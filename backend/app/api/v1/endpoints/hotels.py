import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_tenant_context, require_roles, TenantContext
from app.models.models import User, Hotel, HotelMembership
from app.schemas.schemas import HotelCreate, HotelUpdate, HotelResponse, HotelMembershipCreate, HotelMembershipResponse

router = APIRouter()

def slugify(text: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '-', slug)

@router.get("", response_model=list[HotelResponse])
async def list_my_hotels(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.is_platform_admin:
        res = await db.execute(select(Hotel).where(Hotel.is_active == True))
        return res.scalars().all()

    stmt = (
        select(Hotel)
        .join(HotelMembership, Hotel.id == HotelMembership.hotel_id)
        .where(HotelMembership.user_id == current_user.id, HotelMembership.is_active == True, Hotel.is_active == True)
    )
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=HotelResponse)
async def onboard_hotel(
    data: HotelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    base_slug = slugify(data.name)
    slug = base_slug
    counter = 1
    while True:
        res = await db.execute(select(Hotel).where(Hotel.slug == slug))
        if not res.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    hotel = Hotel(
        name=data.name,
        slug=slug,
        address=data.address,
        city=data.city,
        state=data.state,
        country=data.country,
        postal_code=data.postal_code,
        phone=data.phone,
        email=data.email,
        timezone=data.timezone,
        currency=data.currency,
        check_in_time=data.check_in_time,
        check_out_time=data.check_out_time,
        is_active=True
    )
    db.add(hotel)
    await db.flush()

    # Automatically grant OWNER membership to creator
    membership = HotelMembership(
        user_id=current_user.id,
        hotel_id=hotel.id,
        role="OWNER",
        is_active=True
    )
    db.add(membership)
    await db.commit()
    await db.refresh(hotel)
    return hotel

@router.get("/{hotel_id}", response_model=HotelResponse)
async def get_hotel_profile(
    hotel_id: str,
    ctx: TenantContext = Depends(get_tenant_context)
):
    return ctx.hotel

@router.put("/{hotel_id}", response_model=HotelResponse)
async def update_hotel_profile(
    hotel_id: str,
    data: HotelUpdate,
    ctx: TenantContext = Depends(require_roles(["OWNER"])),
    db: AsyncSession = Depends(get_db)
):
    hotel = ctx.hotel
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(hotel, field, val)
    await db.commit()
    await db.refresh(hotel)
    return hotel

@router.get("/{hotel_id}/members", response_model=list[dict])
async def list_hotel_members(
    hotel_id: str,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER"])),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(HotelMembership, User)
        .join(User, HotelMembership.user_id == User.id)
        .where(HotelMembership.hotel_id == hotel_id, HotelMembership.is_active == True)
    )
    res = await db.execute(stmt)
    results = []
    for m, u in res.all():
        results.append({
            "membership_id": m.id,
            "user_id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "phone_number": u.phone_number,
            "role": m.role,
            "joined_at": m.created_at
        })
    return results

@router.post("/{hotel_id}/members")
async def add_hotel_member(
    hotel_id: str,
    data: HotelMembershipCreate,
    ctx: TenantContext = Depends(require_roles(["OWNER"])),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(User).where(User.email == data.user_email))
    target_user = res.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {data.user_email} not found. Have them register an account first."
        )

    res_mem = await db.execute(
        select(HotelMembership).where(
            HotelMembership.hotel_id == hotel_id,
            HotelMembership.user_id == target_user.id
        )
    )
    existing = res_mem.scalar_one_or_none()
    if existing:
        existing.role = data.role
        existing.is_active = True
    else:
        mem = HotelMembership(
            hotel_id=hotel_id,
            user_id=target_user.id,
            role=data.role,
            is_active=True
        )
        db.add(mem)

    await db.commit()
    return {"message": f"User {data.user_email} added with role {data.role}"}

