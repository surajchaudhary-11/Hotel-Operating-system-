import asyncio
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, or_, and_
from sqlalchemy.exc import IntegrityError
from app.core.timezone import get_hotel_today
from app.models.models import (
    Hotel, Room, GuestStay, Revenue, Payment, Expense, 
    MaintenanceTicket, HousekeepingTask, GeneratedReport, Asset
)

logger = logging.getLogger("hotelos.audit")

class NightAuditService:
    _hotel_locks: Dict[str, asyncio.Lock] = {}
    _lock_loop = None

    @classmethod
    def _get_hotel_lock(cls, hotel_id: str) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if cls._lock_loop != loop:
            cls._hotel_locks.clear()
            cls._lock_loop = loop
        if hotel_id not in cls._hotel_locks:
            cls._hotel_locks[hotel_id] = asyncio.Lock()
        return cls._hotel_locks[hotel_id]

    @classmethod
    async def run_night_audit(
        cls,
        db: AsyncSession,
        hotel_id: str,
        audit_date: date = None
    ) -> Dict[str, Any]:
        hotel_lock = cls._get_hotel_lock(hotel_id)
        async with hotel_lock:
            # 0. Acquire database-level transaction lock (PostgreSQL advisory xact lock or row-level lock)
            try:
                bind_url = str(db.bind.url) if db.bind else ""
                if "postgresql" in bind_url:
                    # Transaction-scoped advisory lock: automatically released when transaction completes
                    await db.execute(
                        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                        {"lock_key": f"night_audit:{hotel_id}"}
                    )
                elif "sqlite" not in bind_url:
                    hotel_stmt = select(Hotel).where(Hotel.id == hotel_id).with_for_update()
                    await db.execute(hotel_stmt)
            except Exception as lock_ex:
                logger.debug(f"Distributed lock note: {lock_ex}")

            h_res = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
            hotel = h_res.scalar_one_or_none()
            hotel_tz = hotel.timezone if hotel else "Asia/Kolkata"

            if not audit_date:
                audit_date = get_hotel_today(hotel_tz)

            # 1. Post Accrual Room Tariff for all active in-house stays with explicit idempotency key
            stmt_stays = (
                select(GuestStay)
                .where(
                    GuestStay.hotel_id == hotel_id,
                    GuestStay.status == "CHECKED_IN"
                )
            )
            res_stays = await db.execute(stmt_stays)
            active_stays = res_stays.scalars().all()

            posted_revenue_count = 0
            for stay in active_stays:
                idempotency_key = f"audit:{hotel_id}:{stay.id}:{audit_date}:ROOM_TARIFF"

                # Check if revenue already posted for this stay and posting_date
                stmt_check = (
                    select(Revenue)
                    .where(
                        or_(
                            Revenue.idempotency_key == idempotency_key,
                            and_(
                                Revenue.hotel_id == hotel_id,
                                Revenue.stay_id == stay.id,
                                Revenue.posting_date == audit_date,
                                Revenue.revenue_type == "ROOM_TARIFF"
                            )
                        )
                    )
                )
                res_check = await db.execute(stmt_check)
                if not res_check.scalars().first():
                    tariff_rev = Revenue(
                        hotel_id=hotel_id,
                        stay_id=stay.id,
                        room_id=stay.room_id,
                        revenue_type="ROOM_TARIFF",
                        amount=stay.room_rate_per_night,
                        tax_amount=round(stay.room_rate_per_night * Decimal("0.12"), 2), # 12% GST
                        posting_date=audit_date,
                        idempotency_key=idempotency_key
                    )
                    db.add(tariff_rev)
                    # Update stay folio balance
                    stay.total_room_charge += stay.room_rate_per_night
                    stay.total_tax_charge += tariff_rev.tax_amount
                    stay.balance_due = (stay.total_room_charge + stay.total_tax_charge + stay.total_additional_charge) - stay.total_paid
                    posted_revenue_count += 1

            try:
                await db.flush()
            except IntegrityError:
                # Concurrent worker already inserted the tariff for this idempotency_key
                logger.info(f"Concurrent night audit detected for hotel {hotel_id} on {audit_date}; rolling back duplicate flush.")
                await db.rollback()
                posted_revenue_count = 0

            # 2. Aggregations for the daily report
            # Room status counts
            stmt_rooms = select(Room).where(Room.hotel_id == hotel_id, Room.is_active == True)
            res_rooms = await db.execute(stmt_rooms)
            all_rooms = res_rooms.scalars().all()
            total_rooms = len(all_rooms)
            occupied_rooms = sum(1 for r in all_rooms if r.status == "OCCUPIED")
            vacant_clean = sum(1 for r in all_rooms if r.status == "VACANT_CLEAN")
            vacant_dirty = sum(1 for r in all_rooms if r.status == "VACANT_DIRTY")
            blocked_maint = sum(1 for r in all_rooms if r.status == "BLOCKED_MAINTENANCE")

            occupancy_rate = round((occupied_rooms / max(1, total_rooms)) * 100, 1)

            # Revenue today
            stmt_rev = (
                select(func.coalesce(func.sum(Revenue.amount), 0))
                .where(Revenue.hotel_id == hotel_id, Revenue.posting_date == audit_date)
            )
            res_rev = await db.execute(stmt_rev)
            today_revenue = Decimal(str(res_rev.scalar_one()))

            # Cash collections today
            stmt_pay = (
                select(func.coalesce(func.sum(Payment.amount), 0))
                .where(
                    Payment.hotel_id == hotel_id,
                    func.date(Payment.payment_date) == audit_date
                )
            )
            res_pay = await db.execute(stmt_pay)
            today_collections = Decimal(str(res_pay.scalar_one()))

            # Expenses recorded today
            stmt_exp = (
                select(func.coalesce(func.sum(Expense.amount), 0))
                .where(Expense.hotel_id == hotel_id, Expense.expense_date == audit_date)
            )
            res_exp = await db.execute(stmt_exp)
            today_expenses = Decimal(str(res_exp.scalar_one()))

            operating_contribution = today_revenue - today_expenses

            # Operations metrics
            stmt_tickets = (
                select(func.count(MaintenanceTicket.id))
                .where(MaintenanceTicket.hotel_id == hotel_id, MaintenanceTicket.status.in_(["REPORTED", "IN_PROGRESS"]))
            )
            res_tickets = await db.execute(stmt_tickets)
            pending_tickets = res_tickets.scalar_one()

            stmt_hk = (
                select(func.count(HousekeepingTask.id))
                .where(HousekeepingTask.hotel_id == hotel_id, HousekeepingTask.status.in_(["PENDING", "IN_PROGRESS", "INSPECTION_PENDING"]))
            )
            res_hk = await db.execute(stmt_hk)
            pending_hk_tasks = res_hk.scalar_one()

            stmt_missing = (
                select(func.count(Asset.id))
                .where(Asset.hotel_id == hotel_id, Asset.condition.in_(["MISSING", "DAMAGED"]))
            )
            res_missing = await db.execute(stmt_missing)
            damaged_or_missing_assets = res_missing.scalar_one()

            report_payload = {
                "hotel_id": hotel_id,
                "report_date": audit_date.isoformat(),
                "occupancy": {
                    "total_rooms": total_rooms,
                    "occupied_rooms": occupied_rooms,
                    "vacant_clean": vacant_clean,
                    "vacant_dirty": vacant_dirty,
                    "blocked_maintenance": blocked_maint,
                    "occupancy_rate_percent": occupancy_rate
                },
                "financials": {
                    "today_earned_revenue_accrual": float(today_revenue),
                    "today_cash_collections": float(today_collections),
                    "today_recorded_expenses": float(today_expenses),
                    "today_operating_contribution": float(operating_contribution),
                    "posted_room_charges_count": posted_revenue_count
                },
                "operations": {
                    "pending_maintenance_tickets": pending_tickets,
                    "pending_housekeeping_tasks": pending_hk_tasks,
                    "damaged_or_missing_assets": damaged_or_missing_assets
                },
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

            # Store in generated_reports table
            stmt_existing = (
                select(GeneratedReport)
                .where(
                    GeneratedReport.hotel_id == hotel_id,
                    GeneratedReport.report_date == audit_date,
                    GeneratedReport.report_type == "DAILY_EOD"
                )
            )
            res_rep = await db.execute(stmt_existing)
            existing_report = res_rep.scalar_one_or_none()

            if existing_report:
                existing_report.report_data = report_payload
                existing_report.generated_at = datetime.now(timezone.utc)
            else:
                new_report = GeneratedReport(
                    hotel_id=hotel_id,
                    report_date=audit_date,
                    report_type="DAILY_EOD",
                    report_data=report_payload
                )
                db.add(new_report)

            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                logger.info(f"Concurrent night audit commit detected for hotel {hotel_id} on {audit_date}; rolled back safely.")
                res_win = await db.execute(stmt_existing)
                win_report = res_win.scalar_one_or_none()
                if win_report:
                    return win_report.report_data

            return report_payload
