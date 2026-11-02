from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.dependencies import get_current_user
from app.models.models import User, HotelMembership, Hotel
from app.schemas.schemas import UserRegister, UserLogin, UserResponse, TokenResponse
from app.core.rate_limit import login_rate_limiter, account_login_rate_limiter, rate_limit_dependency

router = APIRouter()

@router.post("/register", response_model=TokenResponse, dependencies=[Depends(rate_limit_dependency(login_rate_limiter))])
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

@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit_dependency(login_rate_limiter))])
async def login_user(data: UserLogin, db: AsyncSession = Depends(get_db)):
    normalized_email = data.email.strip().lower()
    account_key = f"auth_account:{normalized_email}"

    # Check if account is temporarily throttled due to repeated failed login attempts
    allowed, count, retry_after = await account_login_rate_limiter.check_only(account_key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts for this account. Please try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)}
        )

    res = await db.execute(select(User).where(User.email == normalized_email))
    user = res.scalar_one_or_none()
    
    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        # Record failed attempt against account-level limiter
        await account_login_rate_limiter.record_hit(account_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    # Successful login: reset failed attempt counter for this account
    await account_login_rate_limiter.reset_key(account_key)

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

