from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_tenant_context, require_roles, TenantContext
from app.models.models import UtilityMeter, UtilityReading, Room
from app.schemas.schemas import UtilityMeterCreate, UtilityReadingCreate

router = APIRouter()

@router.get("/meters")
async def list_meters(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(UtilityMeter, Room)
        .outerjoin(Room, UtilityMeter.room_id == Room.id)
        .where(UtilityMeter.hotel_id == ctx.hotel_id)
    )
    res = await db.execute(stmt)
    results = []
    for m, r in res.all():
        results.append({
            "id": m.id,
            "meter_type": m.meter_type,
            "meter_number": m.meter_number,
            "location_name": m.location_name,
            "room_number": r.room_number if r else "Master Hotel Meter"
        })
    return results

@router.post("/meters")
async def create_meter(
    data: UtilityMeterCreate,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER"])),
    db: AsyncSession = Depends(get_db)
):
    meter = UtilityMeter(
        hotel_id=ctx.hotel_id,
        meter_type=data.meter_type,
        room_id=data.room_id,
        meter_number=data.meter_number,
        location_name=data.location_name
    )
    db.add(meter)
    await db.commit()
    await db.refresh(meter)
    return meter

@router.get("/readings")
async def list_readings(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(UtilityReading, UtilityMeter)
        .join(UtilityMeter, UtilityReading.meter_id == UtilityMeter.id)
        .where(UtilityReading.hotel_id == ctx.hotel_id)
        .order_by(UtilityReading.reading_date.desc())
    )
    res = await db.execute(stmt)
    results = []
    for r, m in res.all():
        results.append({
            "id": r.id,
            "meter_type": m.meter_type,
            "meter_number": m.meter_number,
            "location_name": m.location_name,
            "reading_date": r.reading_date,
            "reading_value": float(r.reading_value),
            "consumption_units": float(r.consumption_units),
            "cost_incurred": float(r.cost_incurred),
            "bill_attachment_url": r.bill_attachment_url
        })
    return results

@router.post("/readings")
async def record_reading(
    data: UtilityReadingCreate,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER"])),
    db: AsyncSession = Depends(get_db)
):
    reading = UtilityReading(
        hotel_id=ctx.hotel_id,
        meter_id=data.meter_id,
        reading_date=data.reading_date,
        reading_value=data.reading_value,
        consumption_units=data.consumption_units,
        cost_incurred=data.cost_incurred,
        bill_attachment_url=data.bill_attachment_url
    )
    db.add(reading)
    await db.commit()
    return {"message": "Reading recorded successfully"}

