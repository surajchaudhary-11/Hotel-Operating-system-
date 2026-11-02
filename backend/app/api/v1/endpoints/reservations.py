import re
import uuid
import secrets
import asyncio
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_, and_, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_tenant_context, require_roles, TenantContext
from app.models.models import (
    Guest, GuestStay, Room, RoomType, Floor, Payment, Revenue, Refund, ActivityLog
)
from app.schemas.schemas import (
    ReservationCreate, GroupReservationCreate, ReservationUpdate,
    ReservationCancelRequest, RoomReassignRequest, ReservationPaymentCreate,
    ReservationResponse, TapeChartResponse, TapeChartRoom, TapeChartBlock,
    RoomAvailabilityResponse, RoomAvailabilityItem
)

router = APIRouter()

ALLOWED_ROLES = ["OWNER", "MANAGER", "RECEPTIONIST"]

# SQLite process-level mutual exclusion lock per room
_sqlite_room_locks: dict[str, asyncio.Lock] = {}
_sqlite_locks_guard = asyncio.Lock()


async def get_room_lock(hotel_id: str, room_id: str) -> asyncio.Lock:
    key = f"{hotel_id}:{room_id}"
    async with _sqlite_locks_guard:
        if key not in _sqlite_room_locks:
            _sqlite_room_locks[key] = asyncio.Lock()
        return _sqlite_room_locks[key]


def generate_booking_ref(now: datetime) -> str:
    """Generate human-readable booking reference: BK-YYYYMMDD-XXXX"""
    date_part = now.strftime("%Y%m%d")
    random_part = secrets.token_hex(2).upper()
    return f"BK-{date_part}-{random_part}"


def normalize_datetime(dt: datetime, default_time: time) -> datetime:
    """Ensure datetime has timezone and sensible check-in/checkout hours if default"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def check_room_availability_atomic(
    db: AsyncSession,
    hotel_id: str,
    room_id: str,
    check_in: datetime,
    check_out: datetime,
    exclude_stay_id: Optional[str] = None
) -> Room:
    """
    Checks room existence and verifies half-open interval availability [check_in, check_out).
    PostgreSQL uses row locking (FOR UPDATE) to prevent concurrent double-booking.
    """
    # 1. Fetch room with lock if postgresql
    if db.bind.dialect.name == "postgresql":
        room_stmt = select(Room).where(Room.id == room_id, Room.hotel_id == hotel_id).with_for_update()
        res = await db.execute(room_stmt)
        room = res.scalar_one_or_none()
    else:
        room = await db.get(Room, room_id)
        if room and room.hotel_id != hotel_id:
            room = None

    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with id '{room_id}' not found in this hotel"
        )

    # 2. Overlap query using half-open interval semantics:
    # Overlap occurs when: existing.check_in_time < req_check_out AND existing.expected_check_out_time > req_check_in
    overlap_stmt = (
        select(GuestStay, Guest)
        .join(Guest, GuestStay.guest_id == Guest.id)
        .where(
            GuestStay.hotel_id == hotel_id,
            GuestStay.room_id == room_id,
            GuestStay.status.in_(["RESERVED", "CHECKED_IN"]),
            GuestStay.check_in_time < check_out,
            GuestStay.expected_check_out_time > check_in,
        )
    )
    if exclude_stay_id:
        overlap_stmt = overlap_stmt.where(GuestStay.id != exclude_stay_id)

    res = await db.execute(overlap_stmt)
    overlap = res.first()
    if overlap:
        conflict_stay, conflict_guest = overlap
        conf_in = conflict_stay.check_in_time.strftime("%Y-%m-%d %H:%M")
        conf_out = conflict_stay.expected_check_out_time.strftime("%Y-%m-%d %H:%M")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Room {room.room_number} is already booked by {conflict_guest.full_name} "
                f"from {conf_in} to {conf_out} (Booking #{conflict_stay.booking_reference})"
            )
        )

    return room


def build_reservation_response(stay: GuestStay, guest: Guest, room: Room, room_type: Optional[RoomType], floor: Optional[Floor]) -> ReservationResponse:
    return ReservationResponse(
        id=stay.id,
        hotel_id=stay.hotel_id,
        booking_reference=stay.booking_reference or f"BK-{stay.id[:8].upper()}",
        booking_source=stay.booking_source or "DIRECT",
        external_reference_id=stay.external_reference_id,
        group_booking_id=stay.group_booking_id,
        guest_id=stay.guest_id,
        guest_name=guest.full_name,
        guest_phone=guest.phone,
        guest_email=guest.email,
        room_id=stay.room_id,
        room_number=room.room_number,
        room_type_name=room_type.name if room_type else None,
        floor_name=floor.name if floor else None,
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
        payment_status=stay.payment_status or "UNPAID",
        special_requests=stay.special_requests,
        estimated_arrival_time=stay.estimated_arrival_time,
        cancellation_reason=stay.cancellation_reason,
        registration_token=stay.registration_token,
        created_at=stay.created_at
    )


# -------------------------------------------------------------
# 1. LIST & SEARCH RESERVATIONS
# -------------------------------------------------------------
@router.get("", response_model=List[ReservationResponse])
async def list_reservations(
    search: Optional[str] = Query(None, description="Search by guest name, phone, email, booking ref, or external ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (RESERVED, CHECKED_IN, etc)"),
    booking_source: Optional[str] = Query(None, description="Filter by channel source"),
    start_date: Optional[date] = Query(None, description="Filter check-in on or after date"),
    end_date: Optional[date] = Query(None, description="Filter check-out on or before date"),
    room_id: Optional[str] = Query(None, description="Filter by room"),
    group_booking_id: Optional[str] = Query(None, description="Filter by group ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: TenantContext = Depends(require_roles(ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(GuestStay, Guest, Room, RoomType, Floor)
        .join(Guest, GuestStay.guest_id == Guest.id)
        .join(Room, GuestStay.room_id == Room.id)
        .outerjoin(RoomType, Room.room_type_id == RoomType.id)
        .outerjoin(Floor, Room.floor_id == Floor.id)
        .where(GuestStay.hotel_id == ctx.hotel_id)
    )

    if status_filter:
        stmt = stmt.where(GuestStay.status == status_filter.upper())
    if booking_source:
        stmt = stmt.where(GuestStay.booking_source == booking_source.upper())
    if room_id:
        stmt = stmt.where(GuestStay.room_id == room_id)
    if group_booking_id:
        stmt = stmt.where(GuestStay.group_booking_id == group_booking_id)

    if start_date:
        start_dt = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
        stmt = stmt.where(GuestStay.check_in_time >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date, time.max).replace(tzinfo=timezone.utc)
        stmt = stmt.where(GuestStay.expected_check_out_time <= end_dt)

    if search:
        s = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Guest.full_name.ilike(s),
                Guest.phone.ilike(s),
                Guest.email.ilike(s),
                GuestStay.booking_reference.ilike(s),
                GuestStay.external_reference_id.ilike(s),
                Room.room_number.ilike(s)
            )
        )

    stmt = stmt.order_by(GuestStay.check_in_time.asc(), GuestStay.created_at.desc()).offset(offset).limit(limit)
    res = await db.execute(stmt)

    results = []
    for stay, guest, room, room_type, floor in res.all():
        results.append(build_reservation_response(stay, guest, room, room_type, floor))
    return results


# -------------------------------------------------------------
# 2. TAPE CHART / CALENDAR GRID
# -------------------------------------------------------------
@router.get("/calendar", response_model=TapeChartResponse)
async def get_tape_chart(
    start_date: Optional[date] = Query(None, description="Start date of tape chart window (defaults to today)"),
    days: int = Query(14, ge=1, le=60, description="Number of days to display (default 14, max 60)"),
    ctx: TenantContext = Depends(require_roles(ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    grid_start = start_date or now.date()
    grid_end = grid_start + timedelta(days=days)

    start_dt = datetime.combine(grid_start, time.min).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(grid_end, time.max).replace(tzinfo=timezone.utc)

    # 1. Fetch all rooms for hotel
    rooms_stmt = (
        select(Room, RoomType, Floor)
        .outerjoin(RoomType, Room.room_type_id == RoomType.id)
        .outerjoin(Floor, Room.floor_id == Floor.id)
        .where(Room.hotel_id == ctx.hotel_id, Room.is_active == True)
        .order_by(Floor.floor_number.asc().nulls_first(), Room.room_number.asc())
    )
    rooms_res = await db.execute(rooms_stmt)
    room_rows = rooms_res.all()

    # 2. Fetch all reservations overlapping the calendar window
    stays_stmt = (
        select(GuestStay, Guest, Room)
        .join(Guest, GuestStay.guest_id == Guest.id)
        .join(Room, GuestStay.room_id == Room.id)
        .where(
            GuestStay.hotel_id == ctx.hotel_id,
            GuestStay.check_in_time < end_dt,
            GuestStay.expected_check_out_time > start_dt,
            GuestStay.status.in_(["RESERVED", "CHECKED_IN", "CHECKED_OUT"])
        )
    )
    stays_res = await db.execute(stays_stmt)
    stays = stays_res.all()

    # Group blocks by room_id
    room_blocks_map: dict[str, list[TapeChartBlock]] = {}
    for stay, guest, room in stays:
        block = TapeChartBlock(
            reservation_id=stay.id,
            booking_reference=stay.booking_reference or f"BK-{stay.id[:8].upper()}",
            guest_name=guest.full_name,
            guest_phone=guest.phone,
            room_id=room.id,
            room_number=room.room_number,
            check_in_date=stay.check_in_time.date(),
            check_out_date=stay.expected_check_out_time.date(),
            status=stay.status,
            booking_source=stay.booking_source or "DIRECT",
            payment_status=stay.payment_status or "UNPAID",
            total_paid=stay.total_paid,
            balance_due=stay.balance_due
        )
        room_blocks_map.setdefault(stay.room_id, []).append(block)

    chart_rooms = []
    for room, room_type, floor in room_rows:
        blocks = room_blocks_map.get(room.id, [])
        # sort blocks by check_in_date
        blocks.sort(key=lambda b: b.check_in_date)
        chart_rooms.append(
            TapeChartRoom(
                room_id=room.id,
                room_number=room.room_number,
                room_type=room_type.name if room_type else "Standard",
                floor_name=floor.name if floor else "Floor 1",
                current_status=room.status,
                base_price=room_type.base_price if room_type else Decimal("2500.00"),
                blocks=blocks
            )
        )

    return TapeChartResponse(
        start_date=grid_start,
        end_date=grid_end,
        rooms=chart_rooms
    )


# -------------------------------------------------------------
# 3. AVAILABILITY SEARCH
# -------------------------------------------------------------
@router.get("/availability", response_model=RoomAvailabilityResponse)
async def check_availability(
    check_in_date: date = Query(..., description="Arrival date (YYYY-MM-DD)"),
    check_out_date: date = Query(..., description="Departure date (YYYY-MM-DD)"),
    room_type_id: Optional[str] = Query(None, description="Optional filter by room type"),
    ctx: TenantContext = Depends(require_roles(ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    if check_out_date <= check_in_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-out date must be strictly after check-in date"
        )

    check_in_dt = datetime.combine(check_in_date, time(12, 0)).replace(tzinfo=timezone.utc)
    check_out_dt = datetime.combine(check_out_date, time(11, 0)).replace(tzinfo=timezone.utc)

    # All active rooms in hotel
    room_query = (
        select(Room, RoomType, Floor)
        .outerjoin(RoomType, Room.room_type_id == RoomType.id)
        .outerjoin(Floor, Room.floor_id == Floor.id)
        .where(Room.hotel_id == ctx.hotel_id, Room.is_active == True)
    )
    if room_type_id:
        room_query = room_query.where(Room.room_type_id == room_type_id)

    rooms_res = await db.execute(room_query)
    all_rooms = rooms_res.all()

    # Conflicting room IDs (where active reservation or in-house stay overlaps [check_in, check_out))
    conflicts_stmt = (
        select(GuestStay.room_id)
        .where(
            GuestStay.hotel_id == ctx.hotel_id,
            GuestStay.status.in_(["RESERVED", "CHECKED_IN"]),
            GuestStay.check_in_time < check_out_dt,
            GuestStay.expected_check_out_time > check_in_dt,
        )
        .distinct()
    )
    conflict_res = await db.execute(conflicts_stmt)
    booked_room_ids = set(conflict_res.scalars().all())

    items = []
    avail_count = 0
    for room, room_type, floor in all_rooms:
        is_avail = room.id not in booked_room_ids
        if is_avail:
            avail_count += 1
        items.append(
            RoomAvailabilityItem(
                room_id=room.id,
                room_number=room.room_number,
                floor_name=floor.name if floor else "Floor 1",
                room_type_id=room.room_type_id,
                room_type_name=room_type.name if room_type else "Standard Room",
                base_price=room_type.base_price if room_type else Decimal("2500.00"),
                max_occupancy=room_type.max_occupancy if room_type else 2,
                is_available=is_avail
            )
        )

    # Sort available first, then room number
    items.sort(key=lambda x: (not x.is_available, x.room_number))

    return RoomAvailabilityResponse(
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        total_rooms=len(all_rooms),
        available_rooms_count=avail_count,
        available_rooms=items
    )


# -------------------------------------------------------------
# 4. CREATE SINGLE RESERVATION
# -------------------------------------------------------------
@router.post("", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    data: ReservationCreate,
    ctx: TenantContext = Depends(require_roles(ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    check_in = normalize_datetime(data.check_in_time, time(12, 0))
    check_out = normalize_datetime(data.expected_check_out_time, time(11, 0))

    if check_out <= check_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-out time must be after check-in time"
        )

    room_lock = None
    if db.bind.dialect.name != "postgresql":
        room_lock = await get_room_lock(ctx.hotel_id, data.room_id)
        await room_lock.acquire()

    try:
        # 1. Atomic Availability Check & Room Lock
        room = await check_room_availability_atomic(
            db, ctx.hotel_id, data.room_id, check_in, check_out
        )

        # 2. Resolve or create Guest
        guest = None
        if data.guest_id:
            guest = await db.get(Guest, data.guest_id)
            if not guest or guest.hotel_id != ctx.hotel_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guest not found")
        elif data.guest_info:
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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Guest information is required to create a reservation"
            )

        # 3. Calculate nights, taxes & charges
        nights = max(1, (check_out.date() - check_in.date()).days)
        total_room_charge = data.room_rate_per_night * Decimal(nights)
        tax_amount = round(total_room_charge * Decimal("0.12"), 2)
        total_due = total_room_charge + tax_amount

        advance_paid = max(Decimal("0.00"), data.advance_payment_amount)
        balance_due = max(Decimal("0.00"), total_due - advance_paid)

        payment_status = "UNPAID"
        if advance_paid >= total_due:
            payment_status = "PAID"
        elif advance_paid > Decimal("0.00"):
            payment_status = "PARTIALLY_PAID"

        booking_ref = generate_booking_ref(now)

        # 4. Create GuestStay with status RESERVED
        stay = GuestStay(
            hotel_id=ctx.hotel_id,
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=check_in,
            expected_check_out_time=check_out,
            status="RESERVED",
            adult_count=data.adult_count,
            child_count=data.child_count,
            room_rate_per_night=data.room_rate_per_night,
            total_room_charge=total_room_charge,
            total_tax_charge=tax_amount,
            total_additional_charge=Decimal("0.00"),
            total_paid=advance_paid,
            balance_due=balance_due,
            booking_reference=booking_ref,
            booking_source=data.booking_source.upper(),
            external_reference_id=data.external_reference_id,
            special_requests=data.special_requests,
            estimated_arrival_time=data.estimated_arrival_time,
            payment_status=payment_status
        )
        db.add(stay)
        await db.flush()

        # 5. Handle Advance Deposit Payment (USALI: Liability ledger, not earned revenue yet)
        if advance_paid > Decimal("0.00"):
            payment = Payment(
                hotel_id=ctx.hotel_id,
                stay_id=stay.id,
                amount=advance_paid,
                payment_mode=data.advance_payment_mode or "UPI_QR",
                transaction_reference=f"DEP-{booking_ref}",
                collected_by_user_id=ctx.user.id
            )
            db.add(payment)

        # 6. Audit Log
        audit = ActivityLog(
            hotel_id=ctx.hotel_id,
            user_id=ctx.user.id,
            action_type="CREATE",
            entity_type="STAY",
            entity_id=stay.id,
            details={
                "action": "CREATE_RESERVATION",
                "booking_reference": booking_ref,
                "room_number": room.room_number,
                "source": data.booking_source,
                "nights": nights,
                "advance_paid": str(advance_paid)
            }
        )
        db.add(audit)

        await db.commit()
        await db.refresh(stay)
    finally:
        if room_lock:
            room_lock.release()

    # Fetch room type and floor
    room_type = await db.get(RoomType, room.room_type_id) if room.room_type_id else None
    floor = await db.get(Floor, room.floor_id) if room.floor_id else None

    return build_reservation_response(stay, guest, room, room_type, floor)


# -------------------------------------------------------------
# 5. CREATE GROUP RESERVATION
# -------------------------------------------------------------
@router.post("/group", response_model=List[ReservationResponse], status_code=status.HTTP_201_CREATED)
async def create_group_reservation(
    data: GroupReservationCreate,
    ctx: TenantContext = Depends(require_roles(ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    if not data.rooms:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one room required for group reservation")

    now = datetime.now(timezone.utc)
    check_in = normalize_datetime(data.check_in_time, time(12, 0))
    check_out = normalize_datetime(data.expected_check_out_time, time(11, 0))

    if check_out <= check_in:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Check-out time must be after check-in time")

    # 1. Resolve Primary Guest
    primary_guest = None
    if data.primary_guest_id:
        primary_guest = await db.get(Guest, data.primary_guest_id)
        if not primary_guest or primary_guest.hotel_id != ctx.hotel_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Primary guest not found")
    elif data.primary_guest_info:
        masked_id = data.primary_guest_info.id_number_masked
        if masked_id and len(masked_id) > 4:
            masked_id = "X" * (len(masked_id) - 4) + masked_id[-4:]

        primary_guest = Guest(
            hotel_id=ctx.hotel_id,
            full_name=data.primary_guest_info.full_name,
            email=data.primary_guest_info.email,
            phone=data.primary_guest_info.phone,
            id_type=data.primary_guest_info.id_type or "GOVT_ID",
            id_number_masked=masked_id,
            nationality=data.primary_guest_info.nationality,
            city=data.primary_guest_info.city,
            state=data.primary_guest_info.state
        )
        db.add(primary_guest)
        await db.flush()

    if not primary_guest:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary guest is required")

    group_id = str(uuid.uuid4())
    nights = max(1, (check_out.date() - check_in.date()).days)

    created_stays = []
    # Advance deposit allocation across rooms
    advance_per_room = (data.advance_payment_amount / Decimal(len(data.rooms))) if data.advance_payment_amount > 0 else Decimal("0.00")

    for idx, item in enumerate(data.rooms):
        # Atomic lock & availability check
        room = await check_room_availability_atomic(db, ctx.hotel_id, item.room_id, check_in, check_out)

        # Room occupant guest
        stay_guest = primary_guest
        if item.guest_info:
            stay_guest = Guest(
                hotel_id=ctx.hotel_id,
                full_name=item.guest_info.full_name,
                email=item.guest_info.email,
                phone=item.guest_info.phone,
                id_type=item.guest_info.id_type or "GOVT_ID",
                id_number_masked=item.guest_info.id_number_masked,
                nationality=item.guest_info.nationality,
                city=item.guest_info.city,
                state=item.guest_info.state
            )
            db.add(stay_guest)
            await db.flush()

        room_charge = item.room_rate_per_night * Decimal(nights)
        tax = round(room_charge * Decimal("0.12"), 2)
        total_due = room_charge + tax
        paid = min(advance_per_room, total_due)
        balance = total_due - paid

        pay_status = "PAID" if paid >= total_due else ("PARTIALLY_PAID" if paid > 0 else "UNPAID")
        booking_ref = f"{generate_booking_ref(now)}-{idx + 1}"

        stay = GuestStay(
            hotel_id=ctx.hotel_id,
            guest_id=stay_guest.id,
            room_id=room.id,
            check_in_time=check_in,
            expected_check_out_time=check_out,
            status="RESERVED",
            adult_count=item.adult_count,
            child_count=item.child_count,
            room_rate_per_night=item.room_rate_per_night,
            total_room_charge=room_charge,
            total_tax_charge=tax,
            total_additional_charge=Decimal("0.00"),
            total_paid=paid,
            balance_due=balance,
            booking_reference=booking_ref,
            booking_source=data.booking_source.upper(),
            external_reference_id=data.external_reference_id,
            group_booking_id=group_id,
            special_requests=data.special_requests,
            estimated_arrival_time=data.estimated_arrival_time,
            payment_status=pay_status
        )
        db.add(stay)
        await db.flush()

        if paid > Decimal("0.00"):
            db.add(
                Payment(
                    hotel_id=ctx.hotel_id,
                    stay_id=stay.id,
                    amount=paid,
                    payment_mode=data.advance_payment_mode or "UPI_QR",
                    transaction_reference=f"GRP-DEP-{booking_ref}",
                    collected_by_user_id=ctx.user.id
                )
            )

        created_stays.append((stay, stay_guest, room))

    # Audit Log
    db.add(
        ActivityLog(
            hotel_id=ctx.hotel_id,
            user_id=ctx.user.id,
            action_type="CREATE",
            entity_type="STAY",
            entity_id=group_id,
            details={
                "action": "CREATE_GROUP_RESERVATION",
                "group_booking_id": group_id,
                "room_count": len(created_stays),
                "total_advance_paid": str(data.advance_payment_amount)
            }
        )
    )

    await db.commit()

    responses = []
    for stay, guest, room in created_stays:
        await db.refresh(stay)
        room_type = await db.get(RoomType, room.room_type_id) if room.room_type_id else None
        floor = await db.get(Floor, room.floor_id) if room.floor_id else None
        responses.append(build_reservation_response(stay, guest, room, room_type, floor))

    return responses


# -------------------------------------------------------------
# 6. GET SINGLE RESERVATION DETAILS
# -------------------------------------------------------------
@router.get("/{reservation_id}", response_model=ReservationResponse)
async def get_reservation(
    reservation_id: str,
    ctx: TenantContext = Depends(require_roles(ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(GuestStay, Guest, Room, RoomType, Floor)
        .join(Guest, GuestStay.guest_id == Guest.id)
        .join(Room, GuestStay.room_id == Room.id)
        .outerjoin(RoomType, Room.room_type_id == RoomType.id)
        .outerjoin(Floor, Room.floor_id == Floor.id)
        .where(GuestStay.id == reservation_id, GuestStay.hotel_id == ctx.hotel_id)
    )
    res = await db.execute(stmt)
    record = res.first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")

    stay, guest, room, room_type, floor = record
    return build_reservation_response(stay, guest, room, room_type, floor)


# -------------------------------------------------------------
# 7. EDIT RESERVATION
# -------------------------------------------------------------
@router.put("/{reservation_id}", response_model=ReservationResponse)
async def update_reservation(
    reservation_id: str,
    data: ReservationUpdate,
    ctx: TenantContext = Depends(require_roles(ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    stay = await db.get(GuestStay, reservation_id)
    if not stay or stay.hotel_id != ctx.hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")

    if stay.status not in ["RESERVED", "CHECKED_IN"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit reservation with status '{stay.status}'"
        )

    # If dates changed, re-validate half-open availability
    new_in = normalize_datetime(data.check_in_time, time(12, 0)) if data.check_in_time else stay.check_in_time
    new_out = normalize_datetime(data.expected_check_out_time, time(11, 0)) if data.expected_check_out_time else stay.expected_check_out_time

    if new_out <= new_in:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Check-out time must be after check-in time")

    if data.check_in_time or data.expected_check_out_time:
        await check_room_availability_atomic(
            db, ctx.hotel_id, stay.room_id, new_in, new_out, exclude_stay_id=stay.id
        )
        stay.check_in_time = new_in
        stay.expected_check_out_time = new_out

    if data.room_rate_per_night is not None:
        stay.room_rate_per_night = data.room_rate_per_night

    if data.adult_count is not None:
        stay.adult_count = data.adult_count
    if data.child_count is not None:
        stay.child_count = data.child_count
    if data.booking_source is not None:
        stay.booking_source = data.booking_source.upper()
    if data.external_reference_id is not None:
        stay.external_reference_id = data.external_reference_id
    if data.special_requests is not None:
        stay.special_requests = data.special_requests
    if data.estimated_arrival_time is not None:
        stay.estimated_arrival_time = data.estimated_arrival_time

    # Recalculate totals
    nights = max(1, (stay.expected_check_out_time.date() - stay.check_in_time.date()).days)
    stay.total_room_charge = stay.room_rate_per_night * Decimal(nights)
    stay.total_tax_charge = round(stay.total_room_charge * Decimal("0.12"), 2)
    total_due = stay.total_room_charge + stay.total_tax_charge + stay.total_additional_charge
    stay.balance_due = max(Decimal("0.00"), total_due - stay.total_paid)

    if stay.total_paid >= total_due:
        stay.payment_status = "PAID"
    elif stay.total_paid > Decimal("0.00"):
        stay.payment_status = "PARTIALLY_PAID"
    else:
        stay.payment_status = "UNPAID"

    # Audit Log
    db.add(
        ActivityLog(
            hotel_id=ctx.hotel_id,
            user_id=ctx.user.id,
            action_type="UPDATE",
            entity_type="STAY",
            entity_id=stay.id,
            details={
                "action": "UPDATE_RESERVATION",
                "nights": nights,
                "total_room_charge": str(stay.total_room_charge)
            }
        )
    )

    await db.commit()
    await db.refresh(stay)

    guest = await db.get(Guest, stay.guest_id)
    room = await db.get(Room, stay.room_id)
    room_type = await db.get(RoomType, room.room_type_id) if room.room_type_id else None
    floor = await db.get(Floor, room.floor_id) if room.floor_id else None

    return build_reservation_response(stay, guest, room, room_type, floor)


# -------------------------------------------------------------
# 8. CANCEL RESERVATION
# -------------------------------------------------------------
@router.post("/{reservation_id}/cancel", response_model=ReservationResponse)
async def cancel_reservation(
    reservation_id: str,
    data: ReservationCancelRequest,
    ctx: TenantContext = Depends(require_roles(ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    stay = await db.get(GuestStay, reservation_id)
    if not stay or stay.hotel_id != ctx.hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")

    if stay.status != "RESERVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel booking with status '{stay.status}'. Only 'RESERVED' bookings can be cancelled."
        )

    stay.status = "CANCELLED"
    stay.cancellation_reason = data.cancellation_reason

    # Handle refund if specified
    if data.refund_amount > Decimal("0.00"):
        if data.refund_amount > stay.total_paid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Refund amount ({data.refund_amount}) cannot exceed total paid ({stay.total_paid})"
            )
        refund = Refund(
            hotel_id=ctx.hotel_id,
            stay_id=stay.id,
            amount=data.refund_amount,
            reason=data.refund_reason or f"Cancellation refund: {data.cancellation_reason}",
            approved_by_user_id=ctx.user.id
        )
        db.add(refund)
        stay.total_paid = max(Decimal("0.00"), stay.total_paid - data.refund_amount)
        stay.payment_status = "REFUNDED" if stay.total_paid == 0 else "PARTIALLY_PAID"

    # Audit log
    db.add(
        ActivityLog(
            hotel_id=ctx.hotel_id,
            user_id=ctx.user.id,
            action_type="STATUS_CHANGE",
            entity_type="STAY",
            entity_id=stay.id,
            details={
                "action": "CANCEL_RESERVATION",
                "reason": data.cancellation_reason,
                "refunded": str(data.refund_amount)
            }
        )
    )

    await db.commit()
    await db.refresh(stay)

    guest = await db.get(Guest, stay.guest_id)
    room = await db.get(Room, stay.room_id)
    room_type = await db.get(RoomType, room.room_type_id) if room.room_type_id else None
    floor = await db.get(Floor, room.floor_id) if room.floor_id else None

    return build_reservation_response(stay, guest, room, room_type, floor)


# -------------------------------------------------------------
# 9. CHECK IN RESERVATION (TRANSITION TO IN-HOUSE)
# -------------------------------------------------------------
@router.post("/{reservation_id}/checkin", response_model=ReservationResponse)
async def checkin_reservation(
    reservation_id: str,
    ctx: TenantContext = Depends(require_roles(ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    stay = await db.get(GuestStay, reservation_id)
    if not stay or stay.hotel_id != ctx.hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")

    if stay.status != "RESERVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot check in stay with status '{stay.status}'. Only 'RESERVED' stays can be checked in."
        )

    room = await db.get(Room, stay.room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned room not found")

    now = datetime.now(timezone.utc)
    stay.status = "CHECKED_IN"
    stay.check_in_time = now

    # Update room to OCCUPIED
    room.status = "OCCUPIED"

    # Post initial tariff revenue for day 1 (with idempotency key)
    tax_amount = round(stay.room_rate_per_night * Decimal("0.12"), 2)
    idempotency_key = f"stay:{stay.id}:checkin:{now.date()}:ROOM_TARIFF"

    existing_rev = (
        await db.execute(select(Revenue).where(Revenue.idempotency_key == idempotency_key))
    ).scalar_one_or_none()

    if not existing_rev:
        db.add(
            Revenue(
                hotel_id=ctx.hotel_id,
                stay_id=stay.id,
                room_id=room.id,
                revenue_type="ROOM_TARIFF",
                amount=stay.room_rate_per_night,
                tax_amount=tax_amount,
                posting_date=now.date(),
                idempotency_key=idempotency_key
            )
        )

    # Audit log
    db.add(
        ActivityLog(
            hotel_id=ctx.hotel_id,
            user_id=ctx.user.id,
            action_type="STATUS_CHANGE",
            entity_type="STAY",
            entity_id=stay.id,
            details={
                "action": "CHECK_IN_RESERVATION",
                "room_number": room.room_number,
                "timestamp": now.isoformat()
            }
        )
    )

    await db.commit()
    await db.refresh(stay)

    guest = await db.get(Guest, stay.guest_id)
    room_type = await db.get(RoomType, room.room_type_id) if room.room_type_id else None
    floor = await db.get(Floor, room.floor_id) if room.floor_id else None

    return build_reservation_response(stay, guest, room, room_type, floor)


# -------------------------------------------------------------
# 10. REASSIGN ROOM
# -------------------------------------------------------------
@router.post("/{reservation_id}/reassign", response_model=ReservationResponse)
async def reassign_reservation_room(
    reservation_id: str,
    data: RoomReassignRequest,
    ctx: TenantContext = Depends(require_roles(ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    stay = await db.get(GuestStay, reservation_id)
    if not stay or stay.hotel_id != ctx.hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")

    if stay.status not in ["RESERVED", "CHECKED_IN"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reassign room for stay with status '{stay.status}'"
        )

    if stay.room_id == data.new_room_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stay is already assigned to this room"
        )

    # Atomic availability check on the new room
    new_room = await check_room_availability_atomic(
        db, ctx.hotel_id, data.new_room_id, stay.check_in_time, stay.expected_check_out_time, exclude_stay_id=stay.id
    )

    old_room_id = stay.room_id
    old_room = await db.get(Room, old_room_id)
    stay.room_id = new_room.id

    # If currently checked in, move occupancy status
    if stay.status == "CHECKED_IN":
        if old_room:
            old_room.status = "VACANT_DIRTY"
        new_room.status = "OCCUPIED"

    # Audit log
    db.add(
        ActivityLog(
            hotel_id=ctx.hotel_id,
            user_id=ctx.user.id,
            action_type="UPDATE",
            entity_type="STAY",
            entity_id=stay.id,
            details={
                "action": "REASSIGN_ROOM",
                "old_room_number": old_room.room_number if old_room else None,
                "new_room_number": new_room.room_number,
                "reason": data.reason
            }
        )
    )

    await db.commit()
    await db.refresh(stay)

    guest = await db.get(Guest, stay.guest_id)
    room_type = await db.get(RoomType, new_room.room_type_id) if new_room.room_type_id else None
    floor = await db.get(Floor, new_room.floor_id) if new_room.floor_id else None

    return build_reservation_response(stay, guest, new_room, room_type, floor)


# -------------------------------------------------------------
# 11. RECORD ADVANCE PAYMENT / DEPOSIT
# -------------------------------------------------------------
@router.post("/{reservation_id}/payments", response_model=ReservationResponse)
async def add_reservation_payment(
    reservation_id: str,
    data: ReservationPaymentCreate,
    ctx: TenantContext = Depends(require_roles(ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    if data.amount <= Decimal("0.00"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment amount must be greater than zero")

    stay = await db.get(GuestStay, reservation_id)
    if not stay or stay.hotel_id != ctx.hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")

    if stay.status in ["CANCELLED"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot add payments to cancelled reservations")

    # Record Payment in guest ledger (USALI liability, not earned revenue yet)
    pay = Payment(
        hotel_id=ctx.hotel_id,
        stay_id=stay.id,
        amount=data.amount,
        payment_mode=data.payment_mode,
        transaction_reference=data.transaction_reference or f"DEP-{stay.booking_reference}",
        collected_by_user_id=ctx.user.id
    )
    db.add(pay)

    stay.total_paid += data.amount
    total_due = stay.total_room_charge + stay.total_tax_charge + stay.total_additional_charge
    stay.balance_due = max(Decimal("0.00"), total_due - stay.total_paid)

    if stay.total_paid >= total_due:
        stay.payment_status = "PAID"
    else:
        stay.payment_status = "PARTIALLY_PAID"

    # Audit log
    db.add(
        ActivityLog(
            hotel_id=ctx.hotel_id,
            user_id=ctx.user.id,
            action_type="CREATE",
            entity_type="PAYMENT",
            entity_id=stay.id,
            details={
                "action": "RECORD_PAYMENT",
                "amount": str(data.amount),
                "mode": data.payment_mode,
                "notes": data.notes
            }
        )
    )

    await db.commit()
    await db.refresh(stay)

    guest = await db.get(Guest, stay.guest_id)
    room = await db.get(Room, stay.room_id)
    room_type = await db.get(RoomType, room.room_type_id) if room.room_type_id else None
    floor = await db.get(Floor, room.floor_id) if room.floor_id else None

    return build_reservation_response(stay, guest, room, room_type, floor)
