from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_tenant_context, require_roles, TenantContext
from app.models.models import (
    HousekeepingTask, CleaningChecklist, RoomInspection, Room, User,
    MaintenanceTicket, MaintenanceUpdate, Asset,
    LaundryVendor, LaundryBatch, LaundryItem, AssetCategory, InventoryTransaction
)
from app.schemas.schemas import (
    HousekeepingTaskCreate, ChecklistUpdate, HousekeepingTaskResponse, InspectionSubmit,
    MaintenanceTicketCreate, MaintenanceUpdateCreate, MaintenanceTicketResponse,
    LaundryVendorCreate, LaundryVendorResponse, LaundryBatchDispatch, LaundryBatchReceive
)

router = APIRouter()

# ----------------- HOUSEKEEPING -----------------

@router.get("/housekeeping/tasks", response_model=list[HousekeepingTaskResponse])
async def list_housekeeping_tasks(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(HousekeepingTask, Room, User)
        .join(Room, HousekeepingTask.room_id == Room.id)
        .outerjoin(User, HousekeepingTask.assigned_to_user_id == User.id)
        .where(HousekeepingTask.hotel_id == ctx.hotel_id)
        .order_by(HousekeepingTask.created_at.desc())
    )
    res = await db.execute(stmt)
    results = []
    for task, room, user in res.all():
        # Fetch checklists
        c_res = await db.execute(select(CleaningChecklist).where(CleaningChecklist.task_id == task.id))
        checklists = [
            {"id": c.id, "item_key": c.item_key, "is_completed": c.is_completed}
            for c in c_res.scalars().all()
        ]
        results.append(
            HousekeepingTaskResponse(
                id=task.id,
                hotel_id=task.hotel_id,
                room_id=task.room_id,
                room_number=room.room_number,
                assigned_to_user_id=task.assigned_to_user_id,
                assigned_to_name=user.full_name if user else None,
                status=task.status,
                priority=task.priority,
                started_at=task.started_at,
                completed_at=task.completed_at,
                notes=task.notes,
                created_at=task.created_at,
                checklists=checklists
            )
        )
    return results

@router.post("/housekeeping/tasks", response_model=HousekeepingTaskResponse)
async def create_housekeeping_task(
    data: HousekeepingTaskCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    task = HousekeepingTask(
        hotel_id=ctx.hotel_id,
        room_id=data.room_id,
        assigned_to_user_id=data.assigned_to_user_id or ctx.user.id,
        priority=data.priority,
        notes=data.notes,
        status="PENDING"
    )
    db.add(task)
    await db.flush()

    # Create standard cleaning checklist
    items = [
        "Change bedsheets and pillow covers",
        "Disinfect bathroom surfaces & replenish towels",
        "Dust furniture, sweep and mop floors",
        "Restock complimentary water and toiletries",
        "Inspect all electronics and remote controls"
    ]
    checklists = []
    for item in items:
        c = CleaningChecklist(task_id=task.id, item_key=item, is_completed=False)
        db.add(c)
        checklists.append(c)

    await db.commit()
    await db.refresh(task)

    room = await db.get(Room, task.room_id)
    return HousekeepingTaskResponse(
        id=task.id,
        hotel_id=task.hotel_id,
        room_id=task.room_id,
        room_number=room.room_number if room else None,
        assigned_to_user_id=task.assigned_to_user_id,
        assigned_to_name=ctx.user.full_name,
        status=task.status,
        priority=task.priority,
        started_at=task.started_at,
        completed_at=task.completed_at,
        notes=task.notes,
        created_at=task.created_at,
        checklists=[{"id": c.id, "item_key": c.item_key, "is_completed": c.is_completed} for c in checklists]
    )

@router.patch("/housekeeping/tasks/{task_id}/start")
async def start_housekeeping_task(
    task_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    task = await db.get(HousekeepingTask, task_id)
    if not task or task.hotel_id != ctx.hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task.status = "IN_PROGRESS"
    task.started_at = datetime.now(timezone.utc)
    
    room = await db.get(Room, task.room_id)
    if room and room.status != "OCCUPIED":
        room.status = "VACANT_DIRTY"

    await db.commit()
    return {"message": "Cleaning task started", "status": task.status, "started_at": task.started_at}

@router.patch("/housekeeping/tasks/{task_id}/checklist")
async def toggle_checklist_item(
    task_id: str,
    data: ChecklistUpdate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(CleaningChecklist).where(
            CleaningChecklist.task_id == task_id,
            CleaningChecklist.item_key == data.item_key
        )
    )
    cl = res.scalar_one_or_none()
    if not cl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist item not found")

    cl.is_completed = data.is_completed
    cl.completed_at = datetime.now(timezone.utc) if data.is_completed else None
    await db.commit()
    return {"item_key": cl.item_key, "is_completed": cl.is_completed}

@router.patch("/housekeeping/tasks/{task_id}/complete")
async def complete_housekeeping_task(
    task_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    task = await db.get(HousekeepingTask, task_id)
    if not task or task.hotel_id != ctx.hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task.status = "INSPECTION_PENDING"
    task.completed_at = datetime.now(timezone.utc)

    room = await db.get(Room, task.room_id)
    if room and room.status != "OCCUPIED":
        room.status = "INSPECTION_PENDING"

    await db.commit()
    return {"message": "Room cleaned, queued for supervisor inspection", "status": task.status}

@router.post("/housekeeping/inspections")
async def submit_inspection(
    data: InspectionSubmit,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER"])),
    db: AsyncSession = Depends(get_db)
):
    task = await db.get(HousekeepingTask, data.task_id)
    room = await db.get(Room, data.room_id)
    if not task or not room or task.hotel_id != ctx.hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task or room not found")

    inspection = RoomInspection(
        hotel_id=ctx.hotel_id,
        task_id=task.id,
        room_id=room.id,
        inspector_user_id=ctx.user.id,
        status=data.status,
        rejection_reason=data.rejection_reason
    )
    db.add(inspection)

    if data.status == "PASSED":
        task.status = "READY"
        if room.status != "OCCUPIED":
            room.status = "VACANT_CLEAN"
    else:
        task.status = "INSPECTION_FAILED"
        if room.status != "OCCUPIED":
            room.status = "INSPECTION_FAILED"

    await db.commit()
    return {"status": data.status, "room_status": room.status}

# ----------------- MAINTENANCE -----------------

@router.get("/maintenance/tickets", response_model=list[MaintenanceTicketResponse])
async def list_maintenance_tickets(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(MaintenanceTicket, Room, Asset, User)
        .outerjoin(Room, MaintenanceTicket.room_id == Room.id)
        .outerjoin(Asset, MaintenanceTicket.asset_id == Asset.id)
        .join(User, MaintenanceTicket.reported_by_user_id == User.id)
        .where(MaintenanceTicket.hotel_id == ctx.hotel_id)
        .order_by(MaintenanceTicket.created_at.desc())
    )
    res = await db.execute(stmt)
    results = []
    for t, r, a, u in res.all():
        u_res = await db.execute(select(MaintenanceUpdate).where(MaintenanceUpdate.ticket_id == t.id).order_by(MaintenanceUpdate.created_at))
        updates = [
            {"id": up.id, "message": up.message, "status_change": up.status_change, "cost": float(up.additional_cost), "created_at": up.created_at}
            for up in u_res.scalars().all()
        ]
        results.append(
            MaintenanceTicketResponse(
                id=t.id,
                hotel_id=t.hotel_id,
                room_id=t.room_id,
                room_number=r.room_number if r else None,
                asset_id=t.asset_id,
                asset_name=a.name if a else None,
                title=t.title,
                description=t.description,
                priority=t.priority,
                status=t.status,
                reported_by_name=u.full_name,
                assigned_technician_name=None,
                photo_urls=t.photo_urls,
                estimated_cost=t.estimated_cost,
                actual_cost=t.actual_cost,
                resolved_at=t.resolved_at,
                created_at=t.created_at,
                updates=updates
            )
        )
    return results

@router.post("/maintenance/tickets", response_model=MaintenanceTicketResponse)
async def create_maintenance_ticket(
    data: MaintenanceTicketCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    ticket = MaintenanceTicket(
        hotel_id=ctx.hotel_id,
        room_id=data.room_id,
        asset_id=data.asset_id,
        title=data.title,
        description=data.description,
        priority=data.priority,
        photo_urls=data.photo_urls,
        estimated_cost=data.estimated_cost,
        reported_by_user_id=ctx.user.id,
        status="REPORTED"
    )
    db.add(ticket)

    # If critical priority and attached to room, mark room as BLOCKED_MAINTENANCE
    if data.priority == "CRITICAL" and data.room_id:
        room = await db.get(Room, data.room_id)
        if room and room.status != "OCCUPIED":
            room.status = "BLOCKED_MAINTENANCE"

    await db.commit()
    await db.refresh(ticket)

    room = await db.get(Room, ticket.room_id) if ticket.room_id else None
    asset = await db.get(Asset, ticket.asset_id) if ticket.asset_id else None

    return MaintenanceTicketResponse(
        id=ticket.id,
        hotel_id=ticket.hotel_id,
        room_id=ticket.room_id,
        room_number=room.room_number if room else None,
        asset_id=ticket.asset_id,
        asset_name=asset.name if asset else None,
        title=ticket.title,
        description=ticket.description,
        priority=ticket.priority,
        status=ticket.status,
        reported_by_name=ctx.user.full_name,
        assigned_technician_name=None,
        photo_urls=ticket.photo_urls,
        estimated_cost=ticket.estimated_cost,
        actual_cost=ticket.actual_cost,
        resolved_at=ticket.resolved_at,
        created_at=ticket.created_at,
        updates=[]
    )

@router.post("/maintenance/tickets/{ticket_id}/updates")
async def add_maintenance_update(
    ticket_id: str,
    data: MaintenanceUpdateCreate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    ticket = await db.get(MaintenanceTicket, ticket_id)
    if not ticket or ticket.hotel_id != ctx.hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    up = MaintenanceUpdate(
        ticket_id=ticket.id,
        user_id=ctx.user.id,
        message=data.message,
        status_change=data.status_change,
        additional_cost=data.additional_cost
    )
    db.add(up)

    if data.status_change:
        ticket.status = data.status_change
        if data.status_change == "RESOLVED":
            ticket.resolved_at = datetime.now(timezone.utc)
            # Unblock room if room was blocked
            if ticket.room_id:
                room = await db.get(Room, ticket.room_id)
                if room and room.status == "BLOCKED_MAINTENANCE":
                    room.status = "VACANT_DIRTY" # Needs housekeeping cleaning before guest checkin
    
    if data.additional_cost > 0:
        ticket.actual_cost += data.additional_cost

    await db.commit()
    return {"message": "Update logged successfully", "status": ticket.status, "total_cost": float(ticket.actual_cost)}

# ----------------- LAUNDRY -----------------

@router.get("/laundry/vendors", response_model=list[LaundryVendorResponse])
async def list_laundry_vendors(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(LaundryVendor).where(LaundryVendor.hotel_id == ctx.hotel_id, LaundryVendor.is_active == True))
    return res.scalars().all()

@router.post("/laundry/vendors", response_model=LaundryVendorResponse)
async def create_laundry_vendor(
    data: LaundryVendorCreate,
    ctx: TenantContext = Depends(require_roles(["OWNER", "MANAGER"])),
    db: AsyncSession = Depends(get_db)
):
    v = LaundryVendor(
        hotel_id=ctx.hotel_id,
        name=data.name,
        contact_person=data.contact_person,
        phone=data.phone,
        rate_per_kg=data.rate_per_kg,
        rate_per_piece=data.rate_per_piece,
        is_active=True
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return v

@router.post("/laundry/batches/dispatch")
async def dispatch_laundry_batch(
    data: LaundryBatchDispatch,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    total_sent = sum(item.quantity_sent for item in data.items)
    batch = LaundryBatch(
        hotel_id=ctx.hotel_id,
        vendor_id=data.vendor_id,
        dispatched_by_user_id=ctx.user.id,
        expected_return_date=data.expected_return_date,
        total_items_sent=total_sent,
        status="DISPATCHED"
    )
    db.add(batch)
    await db.flush()

    for item in data.items:
        li = LaundryItem(
            batch_id=batch.id,
            category_id=item.category_id,
            quantity_sent=item.quantity_sent,
            unit_cost=item.unit_cost
        )
        db.add(li)
        
        # Write inventory ledger transaction
        tx = InventoryTransaction(
            hotel_id=ctx.hotel_id,
            category_id=item.category_id,
            transaction_type="DISPATCH_LAUNDRY",
            quantity=item.quantity_sent,
            from_location="STORAGE",
            to_location="LAUNDRY_VENDOR",
            unit_cost=item.unit_cost,
            reference_id=batch.id,
            notes=f"Dispatched in Batch #{batch.id[:8]}",
            performed_by_user_id=ctx.user.id
        )
        db.add(tx)

    await db.commit()
    return {"message": "Laundry batch dispatched successfully", "batch_id": batch.id, "total_items": total_sent}

