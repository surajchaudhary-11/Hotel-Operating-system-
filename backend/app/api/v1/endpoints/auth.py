from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.dependencies import get_current_user
from app.models.models import User, HotelMembership, Hotel
from app.schemas.schemas import UserRegister, UserLogin, UserResponse, TokenResponse

router = APIRouter()

@router.post("/register", response_model=TokenResponse)
async def register_user(data: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    res = await db.execute(select(User).where(User.email == data.email))
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists"
        )
        
    user = User(
        email=data.email,
        full_name=data.full_name,
        phone_number=data.phone_number,
        password_hash=get_password_hash(data.password),
        is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        memberships=[]
    )

@router.post("/login", response_model=TokenResponse)
async def login_user(data: UserLogin, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == data.email))
    user = res.scalar_one_or_none()
    
    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    # Fetch hotel memberships
    stmt = (
        select(HotelMembership, Hotel)
        .join(Hotel, HotelMembership.hotel_id == Hotel.id)
        .where(HotelMembership.user_id == user.id, HotelMembership.is_active == True)
    )
    m_res = await db.execute(stmt)
    memberships = []
    for m, h in m_res.all():
        memberships.append({
            "membership_id": m.id,
            "hotel_id": h.id,
            "hotel_name": h.name,
            "hotel_slug": h.slug,
            "role": m.role,
            "city": h.city
        })

    token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        memberships=memberships
    )

@router.get("/me")
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(HotelMembership, Hotel)
        .join(Hotel, HotelMembership.hotel_id == Hotel.id)
        .where(HotelMembership.user_id == current_user.id, HotelMembership.is_active == True)
    )
    m_res = await db.execute(stmt)
    memberships = []
    for m, h in m_res.all():
        memberships.append({
            "membership_id": m.id,
            "hotel_id": h.id,
            "hotel_name": h.name,
            "hotel_slug": h.slug,
            "role": m.role,
            "city": h.city
        })

    return {
        "user": UserResponse.model_validate(current_user),
        "memberships": memberships
    }

