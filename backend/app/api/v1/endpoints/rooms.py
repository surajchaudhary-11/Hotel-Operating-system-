from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_tenant_context, require_roles, TenantContext
from app.models.models import Floor, RoomType, Room, GuestStay, Guest, Asset, MaintenanceTicket, HousekeepingTask
from app.schemas.schemas import (
    FloorCreate, FloorResponse, RoomTypeCreate, RoomTypeResponse,
    RoomCreate, RoomStatusUpdate, RoomResponse
)

router = APIRouter()

@router.get("", response_model=list[RoomResponse])
async def list_rooms(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Room, Floor, RoomType, Guest.full_name)
        .join(Floor, Room.floor_id == Floor.id)
        .join(RoomType, Room.room_type_id == RoomType.id)
        .outerjoin(
            GuestStay,
            (GuestStay.room_id == Room.id) & (GuestStay.status == "CHECKED_IN") & (GuestStay.hotel_id == ctx.hotel_id)
        )
        .outerjoin(Guest, GuestStay.guest_id == Guest.id)
        .where(Room.hotel_id == ctx.hotel_id, Room.is_active == True)
        .order_by(Floor.floor_number, Room.room_number)
    )
    res = await db.execute(stmt)
    rows = res.all()
    
    results = [
        RoomResponse(
            id=room.id,
            hotel_id=room.hotel_id,
            floor_id=room.floor_id,
            room_type_id=room.room_type_id,
            room_number=room.room_number,
            status=room.status,
            is_active=room.is_active,
            floor_name=floor.name,
            room_type_name=room_type.name,
            base_price=room_type.base_price,
            current_guest_name=guest_name
        )
        for room, floor, room_type, guest_name in rows
    ]
    return results

@router.post("", response_model=RoomResponse)
async def create_room(
    data: RoomCreate,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER"])),
    db: AsyncSession = Depends(get_db)
):
    # Verify room number uniqueness in hotel
    res = await db.execute(select(Room).where(Room.hotel_id == ctx.hotel_id, Room.room_number == data.room_number))
    if res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Room {data.room_number} already exists")

    room = Room(
        hotel_id=ctx.hotel_id,
        floor_id=data.floor_id,
        room_type_id=data.room_type_id,
        room_number=data.room_number,
        status="VACANT_CLEAN",
        is_active=True
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)
    
    floor = await db.get(Floor, room.floor_id)
    rt = await db.get(RoomType, room.room_type_id)

    return RoomResponse(
        id=room.id,
        hotel_id=room.hotel_id,
        floor_id=room.floor_id,
        room_type_id=room.room_type_id,
        room_number=room.room_number,
        status=room.status,
        is_active=room.is_active,
        floor_name=floor.name if floor else None,
        room_type_name=rt.name if rt else None,
        base_price=rt.base_price if rt else None
    )

@router.patch("/{room_id}/status")
async def update_room_status(
    room_id: str,
    data: RoomStatusUpdate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    room = await db.get(Room, room_id)
    if not room or room.hotel_id != ctx.hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    room.status = data.status
    await db.commit()
    return {"room_id": room.id, "status": room.status}

@router.get("/{room_id}/details")
async def get_room_360_details(
    room_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    room = await db.get(Room, room_id)
    if not room or room.hotel_id != ctx.hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    floor = await db.get(Floor, room.floor_id)
    rt = await db.get(RoomType, room.room_type_id)

    # Assets assigned to this room
    res_assets = await db.execute(select(Asset).where(Asset.current_room_id == room.id, Asset.is_active == True))
    assets = res_assets.scalars().all()

    # Active stay
    stmt_stay = select(GuestStay, Guest).join(Guest, GuestStay.guest_id == Guest.id).where(GuestStay.room_id == room.id, GuestStay.status == "CHECKED_IN")
    res_stay = await db.execute(stmt_stay)
    stay_row = res_stay.first()

    # Maintenance tickets
    res_tickets = await db.execute(select(MaintenanceTicket).where(MaintenanceTicket.room_id == room.id).order_by(MaintenanceTicket.created_at.desc()))
    tickets = res_tickets.scalars().all()

    # Housekeeping tasks
    res_hk = await db.execute(select(HousekeepingTask).where(HousekeepingTask.room_id == room.id).order_by(HousekeepingTask.created_at.desc()))
    tasks = res_hk.scalars().all()

    return {
        "room": {
            "id": room.id,
            "room_number": room.room_number,
            "status": room.status,
            "floor_name": floor.name if floor else None,
            "room_type_name": rt.name if rt else None,
            "base_price": float(rt.base_price) if rt else 0.0,
            "amenities": rt.amenities if rt else []
        },
        "current_stay": {
            "stay_id": stay_row[0].id,
            "guest_name": stay_row[1].full_name,
            "phone": stay_row[1].phone,
            "check_in_time": stay_row[0].check_in_time,
            "expected_check_out_time": stay_row[0].expected_check_out_time,
            "balance_due": float(stay_row[0].balance_due)
        } if stay_row else None,
        "assets": [
            {
                "id": a.id,
                "name": a.name,
                "asset_tag": a.asset_tag,
                "condition": a.condition,
                "qr_code_identifier": a.qr_code_identifier
            } for a in assets
        ],
        "recent_tickets": [
            {
                "id": t.id,
                "title": t.title,
                "priority": t.priority,
                "status": t.status,
                "created_at": t.created_at
            } for t in tickets[:5]
        ],
        "recent_cleaning": [
            {
                "id": h.id,
                "status": h.status,
                "started_at": h.started_at,
                "completed_at": h.completed_at
            } for h in tasks[:5]
        ]
    }

# ----------------- FLOORS & ROOM TYPES -----------------

@router.get("/floors", response_model=list[FloorResponse])
async def list_floors(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Floor).where(Floor.hotel_id == ctx.hotel_id).order_by(Floor.floor_number))
    return res.scalars().all()

@router.post("/floors", response_model=FloorResponse)
async def create_floor(
    data: FloorCreate,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER"])),
    db: AsyncSession = Depends(get_db)
):
    floor = Floor(
        hotel_id=ctx.hotel_id,
        floor_number=data.floor_number,
        name=data.name
    )
    db.add(floor)
    await db.commit()
    await db.refresh(floor)
    return floor

@router.get("/room-types", response_model=list[RoomTypeResponse])
async def list_room_types(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(RoomType).where(RoomType.hotel_id == ctx.hotel_id).order_by(RoomType.base_price))
    return res.scalars().all()

@router.post("/room-types", response_model=RoomTypeResponse)
async def create_room_type(
    data: RoomTypeCreate,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER"])),
    db: AsyncSession = Depends(get_db)
):
    rt = RoomType(
        hotel_id=ctx.hotel_id,
        name=data.name,
        base_price=data.base_price,
        max_capacity=data.max_capacity,
        amenities=data.amenities,
        description=data.description
    )
    db.add(rt)
    await db.commit()
    await db.refresh(rt)
    return rt

