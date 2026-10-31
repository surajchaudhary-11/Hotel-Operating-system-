from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.models import Asset, InventoryTransaction
from app.schemas.schemas import InventoryTransactionCreate

class InventoryLedgerService:
    @staticmethod
    async def record_transaction(
        db: AsyncSession,
        hotel_id: str,
        user_id: str,
        data: InventoryTransactionCreate
    ) -> InventoryTransaction:
        asset = None
        if data.asset_id:
            result = await db.execute(
                select(Asset).where(Asset.id == data.asset_id, Asset.hotel_id == hotel_id)
            )
            asset = result.scalar_one_or_none()
            if not asset:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

            # State transition validation and asset update
            if data.transaction_type == "ASSIGN_ROOM":
                asset.current_location_type = "ROOM"
                # to_location can be room_id or room number
                if data.to_location.startswith("room_") or len(data.to_location) == 36:
                    asset.current_room_id = data.to_location
            elif data.transaction_type == "RETURN_STORAGE":
                asset.current_location_type = "STORAGE"
                asset.current_room_id = None
            elif data.transaction_type == "DISPATCH_LAUNDRY":
                asset.current_location_type = "LAUNDRY"
                asset.current_room_id = None
            elif data.transaction_type == "RECEIVE_LAUNDRY":
                asset.current_location_type = "STORAGE"
                asset.current_room_id = None
            elif data.transaction_type == "MARK_DAMAGED":
                asset.condition = "DAMAGED"
            elif data.transaction_type == "MARK_MISSING":
                asset.condition = "MISSING"
            elif data.transaction_type == "DISCARD":
                asset.current_location_type = "SCRAPPED"
                asset.is_active = False

        # Create immutable transaction entry
        tx = InventoryTransaction(
            hotel_id=hotel_id,
            asset_id=data.asset_id,
            category_id=data.category_id,
            transaction_type=data.transaction_type,
            quantity=data.quantity,
            from_location=data.from_location,
            to_location=data.to_location,
            unit_cost=data.unit_cost,
            reference_id=data.reference_id,
            notes=data.notes,
            performed_by_user_id=user_id,
        )
        db.add(tx)
        await db.flush()
        return tx

