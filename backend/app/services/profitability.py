from decimal import Decimal
from typing import List, Dict, Any
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.models import Room, RoomType, Revenue, Expense, MaintenanceTicket, GuestStay
from app.schemas.schemas import RoomProfitabilityItem, ScenarioSimulationRequest, ScenarioSimulationResponse

class ProfitabilityService:
    @staticmethod
    async def get_hotel_room_profitability(
        db: AsyncSession,
        hotel_id: str,
        start_date: date,
        end_date: date
    ) -> List[RoomProfitabilityItem]:
        # 1. Fetch all active rooms with their types
        stmt_rooms = (
            select(Room, RoomType)
            .join(RoomType, Room.room_type_id == RoomType.id)
            .where(Room.hotel_id == hotel_id, Room.is_active == True)
            .order_by(Room.room_number)
        )
        res_rooms = await db.execute(stmt_rooms)
        rooms_data = res_rooms.all()
        
        total_rooms_count = len(rooms_data)
        if total_rooms_count == 0:
            return []

        days_count = max(1, (end_date - start_date).days + 1)

        # 2. Fetch total unallocated operating expenses in this window
        stmt_expenses = (
            select(func.coalesce(func.sum(Expense.amount), 0))
            .where(
                Expense.hotel_id == hotel_id,
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date,
                Expense.room_id == None
            )
        )
        res_expenses = await db.execute(stmt_expenses)
        total_shared_expenses = Decimal(str(res_expenses.scalar_one()))
        allocated_per_room = total_shared_expenses / Decimal(str(total_rooms_count))

        items: List[RoomProfitabilityItem] = []

        for room, room_type in rooms_data:
            available_nights = days_count

            # 3. Earned revenue for this room
            stmt_rev = (
                select(func.coalesce(func.sum(Revenue.amount), 0))
                .where(
                    Revenue.hotel_id == hotel_id,
                    Revenue.room_id == room.id,
                    Revenue.posting_date >= start_date,
                    Revenue.posting_date <= end_date
                )
            )
            res_rev = await db.execute(stmt_rev)
            earned_revenue = Decimal(str(res_rev.scalar_one()))

            # 4. Direct maintenance & repair expenses for this room
            stmt_direct_maint = (
                select(func.coalesce(func.sum(MaintenanceTicket.actual_cost), 0))
                .where(
                    MaintenanceTicket.hotel_id == hotel_id,
                    MaintenanceTicket.room_id == room.id,
                    MaintenanceTicket.status == "RESOLVED"
                )
            )
            res_maint = await db.execute(stmt_direct_maint)
            direct_maint = Decimal(str(res_maint.scalar_one()))

            # Direct room expense from expenses table
            stmt_direct_exp = (
                select(func.coalesce(func.sum(Expense.amount), 0))
                .where(
                    Expense.hotel_id == hotel_id,
                    Expense.room_id == room.id,
                    Expense.expense_date >= start_date,
                    Expense.expense_date <= end_date
                )
            )
            res_direct_exp = await db.execute(stmt_direct_exp)
            direct_exp = Decimal(str(res_direct_exp.scalar_one()))
            total_direct = direct_maint + direct_exp

            # 5. Occupied nights in this window
            stmt_stays = (
                select(GuestStay)
                .where(
                    GuestStay.hotel_id == hotel_id,
                    GuestStay.room_id == room.id,
                    GuestStay.status.in_(["CHECKED_IN", "CHECKED_OUT"])
                )
            )
            res_stays = await db.execute(stmt_stays)
            stays = res_stays.scalars().all()

            # Estimate occupied room nights
            occupied_nights = 0
            for stay in stays:
                stay_start = stay.check_in_time.date()
                stay_end = (stay.actual_check_out_time.date() if stay.actual_check_out_time else stay.expected_check_out_time.date())
                overlap_start = max(start_date, stay_start)
                overlap_end = min(end_date, stay_end)
                if overlap_end >= overlap_start:
                    occupied_nights += (overlap_end - overlap_start).days + 1
            
            occupied_nights = min(occupied_nights, available_nights)
            occ_rate = round((occupied_nights / available_nights) * 100, 1) if available_nights > 0 else 0.0

            # 6. ADR & RevPAR
            adr = round(earned_revenue / Decimal(str(max(1, occupied_nights))), 2) if occupied_nights > 0 else Decimal("0.00")
            revpar = round(earned_revenue / Decimal(str(available_nights)), 2)

            # 7. Operating Contribution (USALI standards)
            operating_contribution = earned_revenue - total_direct - allocated_per_room

            items.append(
                RoomProfitabilityItem(
                    room_id=room.id,
                    room_number=room.room_number,
                    room_type=room_type.name,
                    available_nights=available_nights,
                    occupied_nights=occupied_nights,
                    occupancy_rate=occ_rate,
                    earned_revenue=earned_revenue,
                    direct_maintenance_expenses=total_direct,
                    allocated_expenses=round(allocated_per_room, 2),
                    operating_contribution=round(operating_contribution, 2),
                    adr=adr,
                    revpar=revpar
                )
            )

        return items

    @staticmethod
    def simulate_scenario(req: ScenarioSimulationRequest) -> ScenarioSimulationResponse:
        days = Decimal(str(req.days_in_month))
        occ_fraction = Decimal(str(req.expected_occupancy_rate / 100.0))
        occupied_days = days * occ_fraction
        
        simulated_revenue = req.base_price * occupied_days
        simulated_expenses = req.estimated_maintenance_monthly + req.estimated_allocated_utility_monthly
        simulated_contribution = simulated_revenue - simulated_expenses
        
        simulated_adr = req.base_price if occupied_days > 0 else Decimal("0.00")
        simulated_revpar = round(simulated_revenue / days, 2)
        
        return ScenarioSimulationResponse(
            simulated_monthly_revenue=round(simulated_revenue, 2),
            simulated_operating_expenses=round(simulated_expenses, 2),
            simulated_operating_contribution=round(simulated_contribution, 2),
            simulated_adr=round(simulated_adr, 2),
            simulated_revpar=simulated_revpar
        )

