import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.database import get_db
from app.core.dependencies import get_tenant_context, require_roles, TenantContext
from app.core.rate_limit import digital_checkin_rate_limiter, rate_limit_dependency
from app.services.ai_tools import mask_phone
from app.models.models import Guest, GuestStay, Room, Payment, Revenue, GuestRequest
from app.schemas.schemas import (
    GuestRegistrationRequest, GuestCheckInCreate, GuestCheckOutRequest,
    GuestStayResponse, PaymentCreate
)

router = APIRouter()

@router.get("/stays", response_model=list[GuestStayResponse])
async def list_guest_stays(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(GuestStay, Guest, Room)
        .join(Guest, GuestStay.guest_id == Guest.id)
        .join(Room, GuestStay.room_id == Room.id)
        .where(GuestStay.hotel_id == ctx.hotel_id)
        .order_by(GuestStay.created_at.desc())
    )
    res = await db.execute(stmt)
    results = []
    for stay, guest, room in res.all():
        results.append(
            GuestStayResponse(
                id=stay.id,
                hotel_id=stay.hotel_id,
                guest_id=stay.guest_id,
                guest_name=guest.full_name,
                guest_phone=guest.phone,
                room_id=stay.room_id,
                room_number=room.room_number,
                check_in_time=stay.check_in_time,
                expected_check_out_time=stay.expected_check_out_time,
                actual_check_out_time=stay.actual_check_out_time,
                status=stay.status,
                adult_count=stay.adult_count,
                child_count=stay.child_count,
                room_rate_per_night=stay.room_rate_per_night,
                total_room_charge=stay.total_room_charge,
                total_tax_charge=stay.total_tax_charge,
                total_additional_charge=stay.total_additional_charge,
                total_paid=stay.total_paid,
                balance_due=stay.balance_due,
                registration_token=stay.registration_token
            )
        )
    return results

@router.post("/check-in", response_model=GuestStayResponse)
async def check_in_guest(
    data: GuestCheckInCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    # 1. Resolve or create guest
    guest = None
    if data.guest_id:
        guest = await db.get(Guest, data.guest_id)
    elif data.guest_info:
        # Mask ID if supplied
        masked_id = data.guest_info.id_number_masked
        if masked_id and len(masked_id) > 4:
            masked_id = "X" * (len(masked_id) - 4) + masked_id[-4:]

        guest = Guest(
            hotel_id=ctx.hotel_id,
            full_name=data.guest_info.full_name,
            email=data.guest_info.email,
            phone=data.guest_info.phone,
            id_type=data.guest_info.id_type or "GOVT_ID",
            id_number_masked=masked_id,
            nationality=data.guest_info.nationality,
            city=data.guest_info.city,
            state=data.guest_info.state
        )
        db.add(guest)
        await db.flush()

    if not guest:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Guest information is required")

    # 2. Check room status
    room = await db.get(Room, data.room_id)
    if not room or room.hotel_id != ctx.hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    if room.status not in ["VACANT_CLEAN", "VACANT_DIRTY"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Room {room.room_number} is currently {room.status}")

    now = datetime.now(timezone.utc)
    tax_amount = round(data.room_rate_per_night * Decimal("0.12"), 2)

    stay = GuestStay(
        hotel_id=ctx.hotel_id,
        guest_id=guest.id,
        room_id=room.id,
        check_in_time=now,
        expected_check_out_time=data.expected_check_out_time,
        status="CHECKED_IN",
        adult_count=data.adult_count,
        child_count=data.child_count,
        room_rate_per_night=data.room_rate_per_night,
        total_room_charge=data.room_rate_per_night,
        total_tax_charge=tax_amount,
        total_paid=data.advance_payment_amount,
        balance_due=(data.room_rate_per_night + tax_amount) - data.advance_payment_amount
    )
    db.add(stay)
    await db.flush()

    # Post initial tariff revenue for day 1
    rev = Revenue(
        hotel_id=ctx.hotel_id,
        stay_id=stay.id,
        room_id=room.id,
        revenue_type="ROOM_TARIFF",
        amount=data.room_rate_per_night,
        tax_amount=tax_amount,
        posting_date=now.date()
    )
    db.add(rev)

    # If advance payment collected
    if data.advance_payment_amount > 0:
        pay = Payment(
            hotel_id=ctx.hotel_id,
            stay_id=stay.id,
            amount=data.advance_payment_amount,
            payment_mode=data.advance_payment_mode or "UPI_QR",
            transaction_reference="ADVANCE_CHECKIN",
            collected_by_user_id=ctx.user.id
        )
        db.add(pay)

    # Update room status to OCCUPIED
    room.status = "OCCUPIED"
    await db.commit()
    await db.refresh(stay)

    return GuestStayResponse(
        id=stay.id,
        hotel_id=stay.hotel_id,
        guest_id=stay.guest_id,
        guest_name=guest.full_name,
        guest_phone=guest.phone,
        room_id=stay.room_id,
        room_number=room.room_number,
        check_in_time=stay.check_in_time,
        expected_check_out_time=stay.expected_check_out_time,
        actual_check_out_time=stay.actual_check_out_time,
        status=stay.status,
        adult_count=stay.adult_count,
        child_count=stay.child_count,
        room_rate_per_night=stay.room_rate_per_night,
        total_room_charge=stay.total_room_charge,
        total_tax_charge=stay.total_tax_charge,
        total_additional_charge=stay.total_additional_charge,
        total_paid=stay.total_paid,
        balance_due=stay.balance_due,
        registration_token=stay.registration_token
    )

@router.post("/stays/{stay_id}/checkout")
async def check_out_guest(
    stay_id: str,
    data: GuestCheckOutRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    stay = await db.get(GuestStay, stay_id)
    if not stay or stay.hotel_id != ctx.hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stay not found")

    if data.settlement_payment_amount > 0:
        pay = Payment(
            hotel_id=ctx.hotel_id,
            stay_id=stay.id,
            amount=data.settlement_payment_amount,
            payment_mode=data.settlement_payment_mode,
            transaction_reference="CHECKOUT_SETTLEMENT",
            collected_by_user_id=ctx.user.id
        )
        db.add(pay)
        stay.total_paid += data.settlement_payment_amount
        stay.balance_due -= data.settlement_payment_amount

    now = datetime.now(timezone.utc)
    stay.status = "CHECKED_OUT"
    stay.actual_check_out_time = now

    # Mark room as VACANT_DIRTY for housekeeping
    room = await db.get(Room, stay.room_id)
    if room:
        room.status = "VACANT_DIRTY"

    await db.commit()
    return {"message": "Check-out completed", "stay_id": stay.id, "balance_due": float(stay.balance_due), "room_status": "VACANT_DIRTY"}

# ----------------- TOKENIZED DIGITAL SELF CHECK-IN -----------------

@router.get("/digital-checkin/{token}", dependencies=[Depends(rate_limit_dependency(digital_checkin_rate_limiter))])
async def get_digital_checkin_details(token: str, db: AsyncSession = Depends(get_db)):
    # Check for invalidated tokens
    if token.startswith("used_") or token.startswith("expired_"):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This check-in link has already been used.")

    res = await db.execute(
        select(GuestStay, Guest, Room)
        .join(Guest, GuestStay.guest_id == Guest.id)
        .join(Room, GuestStay.room_id == Room.id)
        .where(GuestStay.registration_token == token)
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired check-in link")

    stay, guest, room = row

    # Disallow accessing completed or cancelled stays
    if stay.status in ["CHECKED_OUT", "CANCELLED", "NO_SHOW"]:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"This check-in link is no longer active (Stay status: {stay.status})."
        )

    # Expiry verification
    now_utc = datetime.now(timezone.utc)
    if stay.expected_check_out_time:
        exp_time = stay.expected_check_out_time
        if exp_time.tzinfo is None:
            exp_time = exp_time.replace(tzinfo=timezone.utc)
        if now_utc > exp_time + timedelta(days=1):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="This check-in link has expired."
            )

    return {
        "stay_id": stay.id,
        "guest_name": guest.full_name,
        "guest_phone": mask_phone(guest.phone), # Redacted to protect guest PII from public URL scraping
        "room_number": room.room_number,
        "check_in_time": stay.check_in_time,
        "expected_check_out_time": stay.expected_check_out_time,
        "total_room_charge": float(stay.total_room_charge),
        "balance_due": float(stay.balance_due),
        "status": stay.status
    }

@router.post("/digital-checkin/{token}/submit", dependencies=[Depends(rate_limit_dependency(digital_checkin_rate_limiter))])
async def submit_digital_checkin(token: str, data: GuestRegistrationRequest, db: AsyncSession = Depends(get_db)):
    if token.startswith("used_") or token.startswith("expired_"):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This check-in link has already been used.")

    res = await db.execute(
        select(GuestStay, Guest)
        .join(Guest, GuestStay.guest_id == Guest.id)
        .where(GuestStay.registration_token == token)
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid registration link")

    stay, guest = row
    if stay.status in ["CHECKED_OUT", "CANCELLED", "NO_SHOW"]:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Registration closed for this stay (Status: {stay.status})."
        )

    # Expiry verification (enforced symmetrically with GET endpoint)
    now_utc = datetime.now(timezone.utc)
    if stay.expected_check_out_time:
        exp_time = stay.expected_check_out_time
        if exp_time.tzinfo is None:
            exp_time = exp_time.replace(tzinfo=timezone.utc)
        if now_utc > exp_time + timedelta(days=1):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="This check-in link has expired."
            )

    # Atomic single-use token consumption via conditional database update
    # Guaranteed to fail if another concurrent request consumed or rotated the token
    new_token = f"used_{uuid.uuid4().hex[:16]}"
    stmt_consume = (
        update(GuestStay)
        .where(
            GuestStay.id == stay.id,
            GuestStay.registration_token == token,
            GuestStay.status.in_(["RESERVED", "CHECKED_IN"])
        )
        .values(registration_token=new_token)
    )
    res_consume = await db.execute(stmt_consume)
    if res_consume.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This check-in link has already been used or expired."
        )

    masked_id = data.id_number_masked
    if masked_id:
        # Aadhaar DPDP compliance: mask all but last 4 digits
        clean_id = re.sub(r'[\s-]', '', masked_id)
        if len(clean_id) >= 4:
            masked_id = "X" * (len(clean_id) - 4) + clean_id[-4:]
        else:
            masked_id = "****"

    guest.full_name = data.full_name
    guest.email = data.email
    guest.phone = data.phone
    guest.id_type = data.id_type
    guest.id_number_masked = masked_id
    guest.city = data.city
    guest.state = data.state

    await db.commit()
    return {"message": "Digital check-in details submitted successfully. Welcome to HotelOS!"}

