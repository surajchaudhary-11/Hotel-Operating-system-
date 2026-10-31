import io
import base64
import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.dependencies import get_tenant_context, require_roles, TenantContext
from app.models.models import AssetCategory, Asset, InventoryTransaction, Room, User
from app.schemas.schemas import (
    AssetCategoryCreate, AssetCategoryResponse,
    AssetCreate, AssetResponse,
    InventoryTransactionCreate, InventoryTransactionResponse
)
from app.services.inventory_ledger import InventoryLedgerService

router = APIRouter()

# ----------------- ASSET CATEGORIES -----------------

@router.get("/categories", response_model=list[AssetCategoryResponse])
async def list_asset_categories(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(AssetCategory, func.count(Asset.id).label("total_assets"))
        .outerjoin(Asset, (Asset.category_id == AssetCategory.id) & (Asset.is_active == True))
        .where(AssetCategory.hotel_id == ctx.hotel_id)
        .group_by(AssetCategory.id)
    )
    res = await db.execute(stmt)
    results = []
    for cat, count in res.all():
        results.append(
            AssetCategoryResponse(
                id=cat.id,
                hotel_id=cat.hotel_id,
                name=cat.name,
                is_linen=cat.is_linen,
                is_consumable=cat.is_consumable,
                low_stock_threshold=cat.low_stock_threshold,
                total_assets_count=count
            )
        )
    return results

@router.post("/categories", response_model=AssetCategoryResponse)
async def create_asset_category(
    data: AssetCategoryCreate,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER"])),
    db: AsyncSession = Depends(get_db)
):
    cat = AssetCategory(
        hotel_id=ctx.hotel_id,
        name=data.name,
        is_linen=data.is_linen,
        is_consumable=data.is_consumable,
        low_stock_threshold=data.low_stock_threshold
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return AssetCategoryResponse(
        id=cat.id,
        hotel_id=cat.hotel_id,
        name=cat.name,
        is_linen=cat.is_linen,
        is_consumable=cat.is_consumable,
        low_stock_threshold=cat.low_stock_threshold,
        total_assets_count=0
    )

# ----------------- ASSETS -----------------

@router.get("/assets", response_model=list[AssetResponse])
async def list_assets(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Asset, AssetCategory, Room)
        .join(AssetCategory, Asset.category_id == AssetCategory.id)
        .outerjoin(Room, Asset.current_room_id == Room.id)
        .where(Asset.hotel_id == ctx.hotel_id, Asset.is_active == True)
        .order_by(Asset.name)
    )
    res = await db.execute(stmt)
    results = []
    for asset, cat, room in res.all():
        results.append(
            AssetResponse(
                id=asset.id,
                hotel_id=asset.hotel_id,
                category_id=asset.category_id,
                name=asset.name,
                asset_tag=asset.asset_tag,
                qr_code_identifier=asset.qr_code_identifier,
                current_location_type=asset.current_location_type,
                current_room_id=asset.current_room_id,
                current_room_number=room.room_number if room else None,
                category_name=cat.name,
                condition=asset.condition,
                purchase_price=asset.purchase_price,
                purchase_date=asset.purchase_date,
                warranty_expiry=asset.warranty_expiry,
                is_active=asset.is_active
            )
        )
    return results

@router.post("/assets", response_model=AssetResponse)
async def create_asset(
    data: AssetCreate,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER"])),
    db: AsyncSession = Depends(get_db)
):
    qr_ident = f"QR-HOTELOS-{ctx.hotel_id[:6]}-{data.name[:3].upper()}-{abs(hash(data.name + str(data.asset_tag))) % 1000000}"
    
    asset = Asset(
        hotel_id=ctx.hotel_id,
        category_id=data.category_id,
        name=data.name,
        asset_tag=data.asset_tag,
        qr_code_identifier=qr_ident,
        current_location_type=data.current_location_type,
        current_room_id=data.current_room_id,
        condition=data.condition,
        purchase_price=data.purchase_price,
        purchase_date=data.purchase_date,
        warranty_expiry=data.warranty_expiry,
        is_active=True
    )
    db.add(asset)
    await db.flush()

    # Automatically record initial PURCHASE inventory transaction
    init_tx = InventoryTransaction(
        hotel_id=ctx.hotel_id,
        asset_id=asset.id,
        category_id=data.category_id,
        transaction_type="PURCHASE",
        quantity=1,
        from_location="VENDOR",
        to_location=data.current_location_type,
        unit_cost=data.purchase_price,
        notes="Initial registration of asset into system",
        performed_by_user_id=ctx.user.id
    )
    db.add(init_tx)
    await db.commit()
    await db.refresh(asset)

    cat = await db.get(AssetCategory, asset.category_id)
    room = await db.get(Room, asset.current_room_id) if asset.current_room_id else None

    return AssetResponse(
        id=asset.id,
        hotel_id=asset.hotel_id,
        category_id=asset.category_id,
        name=asset.name,
        asset_tag=asset.asset_tag,
        qr_code_identifier=asset.qr_code_identifier,
        current_location_type=asset.current_location_type,
        current_room_id=asset.current_room_id,
        current_room_number=room.room_number if room else None,
        category_name=cat.name if cat else None,
        condition=asset.condition,
        purchase_price=asset.purchase_price,
        purchase_date=asset.purchase_date,
        warranty_expiry=asset.warranty_expiry,
        is_active=asset.is_active
    )

# ----------------- IMMUTABLE INVENTORY TRANSACTIONS -----------------

@router.get("/transactions", response_model=list[InventoryTransactionResponse])
async def list_transactions(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(InventoryTransaction, Asset, AssetCategory, User)
        .outerjoin(Asset, InventoryTransaction.asset_id == Asset.id)
        .join(AssetCategory, InventoryTransaction.category_id == AssetCategory.id)
        .join(User, InventoryTransaction.performed_by_user_id == User.id)
        .where(InventoryTransaction.hotel_id == ctx.hotel_id)
        .order_by(InventoryTransaction.created_at.desc())
        .limit(100)
    )
    res = await db.execute(stmt)
    results = []
    for tx, asset, cat, user in res.all():
        results.append(
            InventoryTransactionResponse(
                id=tx.id,
                hotel_id=tx.hotel_id,
                asset_id=tx.asset_id,
                asset_name=asset.name if asset else None,
                category_id=tx.category_id,
                category_name=cat.name,
                transaction_type=tx.transaction_type,
                quantity=tx.quantity,
                from_location=tx.from_location,
                to_location=tx.to_location,
                unit_cost=tx.unit_cost,
                reference_id=tx.reference_id,
                notes=tx.notes,
                performed_by_name=user.full_name,
                created_at=tx.created_at
            )
        )
    return results

@router.post("/transactions", response_model=InventoryTransactionResponse)
async def record_transaction(
    data: InventoryTransactionCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    tx = await InventoryLedgerService.record_transaction(
        db=db,
        hotel_id=ctx.hotel_id,
        user_id=ctx.user.id,
        data=data
    )
    await db.commit()
    await db.refresh(tx)

    asset = await db.get(Asset, tx.asset_id) if tx.asset_id else None
    cat = await db.get(AssetCategory, tx.category_id)

    return InventoryTransactionResponse(
        id=tx.id,
        hotel_id=tx.hotel_id,
        asset_id=tx.asset_id,
        asset_name=asset.name if asset else None,
        category_id=tx.category_id,
        category_name=cat.name if cat else "",
        transaction_type=tx.transaction_type,
        quantity=tx.quantity,
        from_location=tx.from_location,
        to_location=tx.to_location,
        unit_cost=tx.unit_cost,
        reference_id=tx.reference_id,
        notes=tx.notes,
        performed_by_name=ctx.user.full_name,
        created_at=tx.created_at
    )

# ----------------- QR CODE GENERATION -----------------

@router.get("/qr/generate")
async def generate_qr_code(code: str):
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=2,
    )
    qr.add_data(code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0284c7", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")

