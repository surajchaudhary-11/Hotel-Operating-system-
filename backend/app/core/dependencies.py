from typing import Optional, List
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_token
from app.models.models import User, HotelMembership, Hotel

security_bearer = HTTPBearer(auto_error=False)

class TenantContext:
    def __init__(self, hotel_id: str, role: str, hotel: Hotel, user: User):
        self.hotel_id = hotel_id
        self.role = role
        self.hotel = hotel
        self.user = user

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token"
        )
    
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token"
        )
        
    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account deactivated"
        )
        
    return user


async def get_tenant_context(
    x_hotel_id: Optional[str] = Header(None, alias="X-Hotel-ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TenantContext:
    if not x_hotel_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Hotel-ID header is required for hotel-scoped operations"
        )
        
    # Check platform admin override or active hotel membership
    if current_user.is_platform_admin:
        hotel_result = await db.execute(select(Hotel).where(Hotel.id == x_hotel_id, Hotel.is_active == True))
        hotel = hotel_result.scalar_one_or_none()
        if not hotel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
        return TenantContext(hotel_id=x_hotel_id, role="OWNER", hotel=hotel, user=current_user)

    # Query hotel membership
    stmt = (
        select(HotelMembership, Hotel)
        .join(Hotel, HotelMembership.hotel_id == Hotel.id)
        .where(
            HotelMembership.user_id == current_user.id,
            HotelMembership.hotel_id == x_hotel_id,
            HotelMembership.is_active == True,
            Hotel.is_active == True
        )
    )
    result = await db.execute(stmt)
    row = result.first()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have active membership in this hotel"
        )
        
    membership, hotel = row
    return TenantContext(hotel_id=x_hotel_id, role=membership.role, hotel=hotel, user=current_user)


def require_roles(allowed_roles: List[str]):
    def role_checker(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if ctx.user.is_platform_admin or ctx.role == "OWNER":
            return ctx
        if ctx.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{ctx.role}'. Required: {allowed_roles}"
            )
        return ctx
    return role_checker

