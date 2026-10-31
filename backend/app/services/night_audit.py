from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.models import (
    Room, GuestStay, Revenue, Payment, Expense, 
    MaintenanceTicket, HousekeepingTask, GeneratedReport, Asset
)

class NightAuditService:
    @staticmethod
    async def run_night_audit(
        db: AsyncSession,
        hotel_id: str,
        audit_date: date = None
    ) -> Dict[str, Any]:
        if not audit_date:
            audit_date = date.today()

        # 1. Post Accrual Room Tariff for all active in-house stays
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
            # Check if revenue already posted for this stay and posting_date
            stmt_check = (
                select(Revenue)
                .where(
                    Revenue.hotel_id == hotel_id,
                    Revenue.stay_id == stay.id,
                    Revenue.posting_date == audit_date,
                    Revenue.revenue_type == "ROOM_TARIFF"
                )
            )
            res_check = await db.execute(stmt_check)
            if not res_check.scalar_one_or_none():
                tariff_rev = Revenue(
                    hotel_id=hotel_id,
                    stay_id=stay.id,
                    room_id=stay.room_id,
                    revenue_type="ROOM_TARIFF",
                    amount=stay.room_rate_per_night,
                    tax_amount=round(stay.room_rate_per_night * Decimal("0.12"), 2), # 12% GST
                    posting_date=audit_date
                )
                db.add(tariff_rev)
                # Update stay folio balance
                stay.total_room_charge += stay.room_rate_per_night
                stay.total_tax_charge += tariff_rev.tax_amount
                stay.balance_due = (stay.total_room_charge + stay.total_tax_charge + stay.total_additional_charge) - stay.total_paid
                posted_revenue_count += 1

        await db.flush()

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

        await db.commit()
        return report_payload

