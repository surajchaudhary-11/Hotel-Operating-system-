from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.dependencies import get_tenant_context, require_roles, TenantContext
from app.models.models import (
    Expense, ExpenseCategory, Revenue, Payment, Room, MaintenanceTicket
)
from app.schemas.schemas import (
    ExpenseCreate, ExpenseResponse, ExpenseCategoryCreate, ExpenseCategoryResponse,
    FinancialSummaryResponse, RoomProfitabilityItem, ScenarioSimulationRequest, ScenarioSimulationResponse
)
from app.services.profitability import ProfitabilityService
from app.core.timezone import get_hotel_today

router = APIRouter()

@router.get("/summary", response_model=FinancialSummaryResponse)
async def get_financial_summary(
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER", "ACCOUNTANT"])),
    db: AsyncSession = Depends(get_db)
):
    today = get_hotel_today(ctx.hotel.timezone if ctx.hotel else "Asia/Kolkata")
    month_start = today.replace(day=1)

    # Today's earned revenue
    res_td_rev = await db.execute(select(func.coalesce(func.sum(Revenue.amount), 0)).where(Revenue.hotel_id == ctx.hotel_id, Revenue.posting_date == today))
    td_rev = Decimal(str(res_td_rev.scalar_one()))

    # Today's cash collections
    res_td_pay = await db.execute(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.hotel_id == ctx.hotel_id, func.date(Payment.payment_date) == today))
    td_pay = Decimal(str(res_td_pay.scalar_one()))

    # Today's expenses
    res_td_exp = await db.execute(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.hotel_id == ctx.hotel_id, Expense.expense_date == today))
    td_exp = Decimal(str(res_td_exp.scalar_one()))

    td_op_contrib = td_rev - td_exp

    # MTD revenue
    res_mtd_rev = await db.execute(select(func.coalesce(func.sum(Revenue.amount), 0)).where(Revenue.hotel_id == ctx.hotel_id, Revenue.posting_date >= month_start))
    mtd_rev = Decimal(str(res_mtd_rev.scalar_one()))

    # MTD collections
    res_mtd_pay = await db.execute(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.hotel_id == ctx.hotel_id, func.date(Payment.payment_date) >= month_start))
    mtd_pay = Decimal(str(res_mtd_pay.scalar_one()))

    # MTD expenses
    res_mtd_exp = await db.execute(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.hotel_id == ctx.hotel_id, Expense.expense_date >= month_start))
    mtd_exp = Decimal(str(res_mtd_exp.scalar_one()))

    mtd_op_contrib = mtd_rev - mtd_exp

    # Room occupancy
    res_rooms = await db.execute(select(Room).where(Room.hotel_id == ctx.hotel_id, Room.is_active == True))
    rooms = res_rooms.scalars().all()
    total_rooms = len(rooms)
    occupied_rooms = sum(1 for r in rooms if r.status == "OCCUPIED")
    vacant_rooms = sum(1 for r in rooms if r.status in ["VACANT_CLEAN", "VACANT_DIRTY", "INSPECTION_PENDING", "INSPECTION_FAILED"])
    maintenance_rooms = sum(1 for r in rooms if r.status == "BLOCKED_MAINTENANCE")
    occ_rate = round((occupied_rooms / max(1, total_rooms)) * 100, 1)

    return FinancialSummaryResponse(
        today_revenue=td_rev,
        today_collections=td_pay,
        today_expenses=td_exp,
        today_operating_contribution=td_op_contrib,
        mtd_revenue=mtd_rev,
        mtd_collections=mtd_pay,
        mtd_expenses=mtd_exp,
        mtd_operating_contribution=mtd_op_contrib,
        occupancy_rate=occ_rate,
        total_rooms=total_rooms,
        occupied_rooms=occupied_rooms,
        vacant_rooms=vacant_rooms,
        maintenance_rooms=maintenance_rooms
    )

# ----------------- EXPENSES -----------------

@router.get("/expenses", response_model=list[ExpenseResponse])
async def list_expenses(
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER", "ACCOUNTANT"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Expense, ExpenseCategory, Room)
        .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .outerjoin(Room, Expense.room_id == Room.id)
        .where(Expense.hotel_id == ctx.hotel_id)
        .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
    )
    res = await db.execute(stmt)
    results = []
    for exp, cat, room in res.all():
        results.append(
            ExpenseResponse(
                id=exp.id,
                hotel_id=exp.hotel_id,
                category_id=exp.category_id,
                category_name=cat.name,
                room_id=exp.room_id,
                room_number=room.room_number if room else None,
                amount=exp.amount,
                expense_date=exp.expense_date,
                payment_method=exp.payment_method,
                invoice_url=exp.invoice_url,
                description=exp.description,
                is_allocated=exp.is_allocated,
                created_at=exp.created_at
            )
        )
    return results

@router.post("/expenses", response_model=ExpenseResponse)
async def create_expense(
    data: ExpenseCreate,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER", "ACCOUNTANT"])),
    db: AsyncSession = Depends(get_db)
):
    exp = Expense(
        hotel_id=ctx.hotel_id,
        category_id=data.category_id,
        room_id=data.room_id,
        amount=data.amount,
        expense_date=data.expense_date,
        payment_method=data.payment_method,
        invoice_url=data.invoice_url,
        description=data.description,
        is_allocated=(data.room_id is None), # True if shared property-wide expense
        approved_by_user_id=ctx.user.id
    )
    db.add(exp)
    await db.commit()
    await db.refresh(exp)

    cat = await db.get(ExpenseCategory, exp.category_id)
    room = await db.get(Room, exp.room_id) if exp.room_id else None

    return ExpenseResponse(
        id=exp.id,
        hotel_id=exp.hotel_id,
        category_id=exp.category_id,
        category_name=cat.name if cat else "",
        room_id=exp.room_id,
        room_number=room.room_number if room else None,
        amount=exp.amount,
        expense_date=exp.expense_date,
        payment_method=exp.payment_method,
        invoice_url=exp.invoice_url,
        description=exp.description,
        is_allocated=exp.is_allocated,
        created_at=exp.created_at
    )

@router.get("/categories", response_model=list[ExpenseCategoryResponse])
async def list_expense_categories(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(ExpenseCategory).where(ExpenseCategory.hotel_id == ctx.hotel_id))
    return res.scalars().all()

# ----------------- ROOM PROFITABILITY & SCENARIOS -----------------

@router.get("/room-profitability", response_model=list[RoomProfitabilityItem])
async def get_room_profitability(
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER", "ACCOUNTANT"])),
    db: AsyncSession = Depends(get_db)
):
    today = get_hotel_today(ctx.hotel.timezone if ctx.hotel else "Asia/Kolkata")
    start_date = today.replace(day=1) # Month to date
    return await ProfitabilityService.get_hotel_room_profitability(
        db=db,
        hotel_id=ctx.hotel_id,
        start_date=start_date,
        end_date=today
    )

@router.post("/scenario-simulation", response_model=ScenarioSimulationResponse)
async def simulate_scenario(data: ScenarioSimulationRequest):
    return ProfitabilityService.simulate_scenario(data)

