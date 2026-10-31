from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, hotels, rooms, inventory, operations, guests, finance, reports, ai, utilities
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(hotels.router, prefix="/hotels", tags=["Hotels & Multi-Tenancy"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["Rooms & Floors"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory & Assets"])
api_router.include_router(operations.router, prefix="/operations", tags=["Operations"])
api_router.include_router(guests.router, prefix="/guests", tags=["Guests & Stays"])
api_router.include_router(finance.router, prefix="/finance", tags=["Finance & Profitability"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reporting"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI Hotel Assistant"])
api_router.include_router(utilities.router, prefix="/utilities", tags=["Energy & Utilities"])

