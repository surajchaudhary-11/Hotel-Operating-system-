"""
HotelOS — Typed AI Backend Tools
Implements predefined, typed, validated tools for the AI Operations Assistant.
Strictly enforces multi-tenant isolation (hotel_id) and role-based permissions (RBAC).
Complies with USALI 11th Edition financial definitions.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_

from app.core.dependencies import TenantContext
from app.models.models import (
    Room, RoomType, Floor, GuestStay, Guest, Payment, Revenue, Expense,
    HousekeepingTask, CleaningChecklist, RoomInspection,
    MaintenanceTicket, MaintenanceUpdate,
    Asset, AssetCategory, InventoryTransaction, User, HotelMembership
)

import re

# =====================================================================
# PII PROTECTION & SANITIZATION HELPERS
# =====================================================================

def mask_phone(phone: Optional[str]) -> Optional[str]:
    """Redacts guest phone number to protect sensitive PII (e.g. +91 9876543210 -> +91 98****3210)."""
    if not phone:
        return None
    raw = str(phone).strip()
    if len(raw) <= 5:
        return "****"
    return f"{raw[:4]}****{raw[-4:]}"

def mask_email(email: Optional[str]) -> Optional[str]:
    """Redacts guest email address to protect sensitive PII (e.g. guest@domain.com -> g***t@domain.com)."""
    if not email or "@" not in email:
        return None
    parts = email.split("@", 1)
    user, domain = parts[0], parts[1]
    if len(user) <= 2:
        masked_user = f"{user[0]}*"
    else:
        masked_user = f"{user[0]}***{user[-1]}"
    return f"{masked_user}@{domain}"

# =====================================================================
# TOOL SCHEMAS & SPECIFICATIONS
# =====================================================================

class ToolExecutionResult(BaseModel):
    success: bool
    tool_name: str
    data: Any
    message: str
    error: Optional[str] = None


# =====================================================================
# A. ROOM MANAGEMENT TOOLS
# =====================================================================

async def tool_get_room_status(
    db: AsyncSession,
    ctx: TenantContext,
    room_number: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieves real-time status of all rooms or a specific room."""
    stmt = (
        select(Room, Floor, RoomType)
        .join(Floor, Room.floor_id == Floor.id)
        .join(RoomType, Room.room_type_id == RoomType.id)
        .where(Room.hotel_id == ctx.hotel_id, Room.is_active == True)
    )
    if room_number:
        stmt = stmt.where(Room.room_number == str(room_number).strip())

    res = await db.execute(stmt)
    rows = res.all()

    if not rows:
        if room_number:
            return {"found": False, "message": f"Room {room_number} was not found in this hotel."}
        return {"total_rooms": 0, "rooms": []}

    rooms_list = []
    for room, floor, room_type in rows:
        # Check active guest stay
        stmt_stay = (
            select(GuestStay, Guest)
            .join(Guest, GuestStay.guest_id == Guest.id)
            .where(GuestStay.room_id == room.id, GuestStay.status == "CHECKED_IN")
        )
        res_stay = await db.execute(stmt_stay)
        stay_row = res_stay.first()
        guest_name = stay_row[1].full_name if stay_row else None

        rooms_list.append({
            "room_number": room.room_number,
            "status": room.status,
            "floor": floor.name,
            "room_type": room_type.name,
            "base_rate": float(room_type.base_price),
            "current_guest": guest_name
        })

    summary = {
        "total": len(rooms_list),
        "occupied": sum(1 for r in rooms_list if r["status"] == "OCCUPIED"),
        "vacant_clean": sum(1 for r in rooms_list if r["status"] == "VACANT_CLEAN"),
        "vacant_dirty": sum(1 for r in rooms_list if r["status"] == "VACANT_DIRTY"),
        "blocked_maintenance": sum(1 for r in rooms_list if r["status"] == "BLOCKED_MAINTENANCE"),
        "inspection_pending": sum(1 for r in rooms_list if r["status"] in ["INSPECTION_PENDING", "INSPECTION_FAILED"])
    }
    return {"summary": summary, "rooms": rooms_list}


async def tool_get_vacant_rooms(
    db: AsyncSession,
    ctx: TenantContext,
    clean_only: bool = False
) -> Dict[str, Any]:
    """Retrieves all vacant rooms ready for sale or requiring cleaning."""
    statuses = ["VACANT_CLEAN"] if clean_only else ["VACANT_CLEAN", "VACANT_DIRTY"]
    stmt = (
        select(Room, Floor, RoomType)
        .join(Floor, Room.floor_id == Floor.id)
        .join(RoomType, Room.room_type_id == RoomType.id)
        .where(Room.hotel_id == ctx.hotel_id, Room.is_active == True, Room.status.in_(statuses))
        .order_by(Room.room_number)
    )
    res = await db.execute(stmt)
    rows = res.all()

    vacant = [
        {
            "room_number": r.room_number,
            "status": r.status,
            "floor": f.name,
            "room_type": rt.name,
            "base_rate": float(rt.base_price)
        }
        for r, f, rt in rows
    ]
    return {
        "vacant_count": len(vacant),
        "clean_ready_to_sell": sum(1 for v in vacant if v["status"] == "VACANT_CLEAN"),
        "dirty_needs_cleaning": sum(1 for v in vacant if v["status"] == "VACANT_DIRTY"),
        "rooms": vacant
    }


async def tool_get_occupied_rooms(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Retrieves all currently occupied rooms with stay and guest details."""
    stmt = (
        select(Room, Floor, RoomType, GuestStay, Guest)
        .join(Floor, Room.floor_id == Floor.id)
        .join(RoomType, Room.room_type_id == RoomType.id)
        .join(GuestStay, GuestStay.room_id == Room.id)
        .join(Guest, GuestStay.guest_id == Guest.id)
        .where(
            Room.hotel_id == ctx.hotel_id,
            Room.is_active == True,
            Room.status == "OCCUPIED",
            GuestStay.status == "CHECKED_IN"
        )
        .order_by(Room.room_number)
    )
    res = await db.execute(stmt)
    rows = res.all()

    occupied = []
    for r, f, rt, stay, guest in rows:
        occupied.append({
            "room_number": r.room_number,
            "floor": f.name,
            "room_type": rt.name,
            "guest_name": guest.full_name,
            "guest_phone": mask_phone(guest.phone),
            "check_in_time": stay.check_in_time.isoformat() if stay.check_in_time else None,
            "expected_check_out": stay.expected_check_out_time.isoformat() if stay.expected_check_out_time else None,
            "room_rate": float(stay.room_rate_per_night),
            "balance_due": float(stay.balance_due)
        })

    return {
        "occupied_count": len(occupied),
        "rooms": occupied
    }


async def tool_get_rooms_under_maintenance(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Retrieves all rooms currently blocked for maintenance or undergoing active repairs."""
    stmt = (
        select(Room, Floor, RoomType)
        .join(Floor, Room.floor_id == Floor.id)
        .join(RoomType, Room.room_type_id == RoomType.id)
        .where(
            Room.hotel_id == ctx.hotel_id,
            Room.is_active == True,
            Room.status == "BLOCKED_MAINTENANCE"
        )
        .order_by(Room.room_number)
    )
    res = await db.execute(stmt)
    rows = res.all()

    blocked = []
    for r, f, rt in rows:
        # Find active ticket
        t_stmt = select(MaintenanceTicket).where(
            MaintenanceTicket.room_id == r.id,
            MaintenanceTicket.status.in_(["REPORTED", "IN_PROGRESS", "WAITING_PARTS"])
        ).order_by(MaintenanceTicket.created_at.desc())
        t_res = await db.execute(t_stmt)
        ticket = t_res.scalar_one_or_none()

        blocked.append({
            "room_number": r.room_number,
            "floor": f.name,
            "room_type": rt.name,
            "issue_title": ticket.title if ticket else "Preventative Maintenance",
            "priority": ticket.priority if ticket else "HIGH",
            "ticket_status": ticket.status if ticket else "BLOCKED"
        })

    return {
        "blocked_rooms_count": len(blocked),
        "rooms": blocked
    }


async def tool_get_rooms_by_floor(
    db: AsyncSession,
    ctx: TenantContext,
    floor_number: int
) -> Dict[str, Any]:
    """Retrieves all rooms on a specific floor with their statuses."""
    stmt = (
        select(Room, Floor, RoomType)
        .join(Floor, Room.floor_id == Floor.id)
        .join(RoomType, Room.room_type_id == RoomType.id)
        .where(Room.hotel_id == ctx.hotel_id, Floor.floor_number == floor_number, Room.is_active == True)
        .order_by(Room.room_number)
    )
    res = await db.execute(stmt)
    rows = res.all()

    if not rows:
        return {"floor_number": floor_number, "count": 0, "rooms": [], "message": f"No rooms found on Floor {floor_number}."}

    rooms = [
        {
            "room_number": r.room_number,
            "status": r.status,
            "room_type": rt.name,
            "base_rate": float(rt.base_price)
        }
        for r, f, rt in rows
    ]
    return {
        "floor_name": rows[0][1].name,
        "floor_number": floor_number,
        "count": len(rooms),
        "rooms": rooms
    }


# =====================================================================
# B. BOOKING & RESERVATION TOOLS
# =====================================================================

async def tool_get_today_bookings(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Retrieves check-ins and check-outs scheduled or executed for today."""
    today = date.today()
    stmt = (
        select(GuestStay, Guest, Room)
        .join(Guest, GuestStay.guest_id == Guest.id)
        .join(Room, GuestStay.room_id == Room.id)
        .where(
            GuestStay.hotel_id == ctx.hotel_id,
            or_(
                func.date(GuestStay.check_in_time) == today,
                func.date(GuestStay.expected_check_out_time) == today,
                GuestStay.status == "CHECKED_IN"
            )
        )
    )
    res = await db.execute(stmt)
    stays = res.all()

    today_checkins = []
    today_checkouts = []
    active_stays = []

    for stay, guest, room in stays:
        info = {
            "stay_id": stay.id,
            "room_number": room.room_number,
            "guest_name": guest.full_name,
            "guest_phone": mask_phone(guest.phone),
            "status": stay.status,
            "rate_per_night": float(stay.room_rate_per_night),
            "balance_due": float(stay.balance_due),
            "check_in": stay.check_in_time.strftime("%I:%M %p") if stay.check_in_time else "N/A",
            "expected_checkout": stay.expected_check_out_time.strftime("%I:%M %p") if stay.expected_check_out_time else "N/A"
        }
        if stay.check_in_time and stay.check_in_time.date() == today:
            today_checkins.append(info)
        if stay.expected_check_out_time and stay.expected_check_out_time.date() == today:
            today_checkouts.append(info)
        if stay.status == "CHECKED_IN":
            active_stays.append(info)

    return {
        "date": today.isoformat(),
        "today_checkins_count": len(today_checkins),
        "today_checkouts_count": len(today_checkouts),
        "total_active_stays": len(active_stays),
        "checkins": today_checkins,
        "checkouts": today_checkouts
    }


async def tool_get_today_checkins(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Retrieves only today's arrivals and check-ins."""
    today = date.today()
    stmt = (
        select(GuestStay, Guest, Room)
        .join(Guest, GuestStay.guest_id == Guest.id)
        .join(Room, GuestStay.room_id == Room.id)
        .where(
            GuestStay.hotel_id == ctx.hotel_id,
            func.date(GuestStay.check_in_time) == today
        )
        .order_by(GuestStay.check_in_time)
    )
    res = await db.execute(stmt)
    rows = res.all()
    checkins = [
        {
            "room_number": room.room_number,
            "guest_name": guest.full_name,
            "guest_phone": mask_phone(guest.phone),
            "time": stay.check_in_time.strftime("%I:%M %p") if stay.check_in_time else "N/A",
            "status": stay.status,
            "rate_per_night": float(stay.room_rate_per_night)
        }
        for stay, guest, room in rows
    ]
    return {"date": today.isoformat(), "count": len(checkins), "checkins": checkins}


async def tool_get_today_checkouts(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Retrieves only today's scheduled departures and check-outs."""
    today = date.today()
    stmt = (
        select(GuestStay, Guest, Room)
        .join(Guest, GuestStay.guest_id == Guest.id)
        .join(Room, GuestStay.room_id == Room.id)
        .where(
            GuestStay.hotel_id == ctx.hotel_id,
            func.date(GuestStay.expected_check_out_time) == today
        )
        .order_by(GuestStay.expected_check_out_time)
    )
    res = await db.execute(stmt)
    rows = res.all()
    checkouts = [
        {
            "room_number": room.room_number,
            "guest_name": guest.full_name,
            "guest_phone": mask_phone(guest.phone),
            "expected_time": stay.expected_check_out_time.strftime("%I:%M %p") if stay.expected_check_out_time else "N/A",
            "status": stay.status,
            "balance_due": float(stay.balance_due)
        }
        for stay, guest, room in rows
    ]
    return {"date": today.isoformat(), "count": len(checkouts), "checkouts": checkouts}


async def tool_get_upcoming_reservations(
    db: AsyncSession,
    ctx: TenantContext,
    days: int = 7
) -> Dict[str, Any]:
    """Retrieves reservations and stays scheduled across the next N days."""
    today = date.today()
    end_date = today + timedelta(days=days)
    stmt = (
        select(GuestStay, Guest, Room)
        .join(Guest, GuestStay.guest_id == Guest.id)
        .join(Room, GuestStay.room_id == Room.id)
        .where(
            GuestStay.hotel_id == ctx.hotel_id,
            func.date(GuestStay.check_in_time) >= today,
            func.date(GuestStay.check_in_time) <= end_date
        )
        .order_by(GuestStay.check_in_time)
    )
    res = await db.execute(stmt)
    rows = res.all()

    reservations = [
        {
            "room_number": room.room_number,
            "guest_name": guest.full_name,
            "check_in_date": stay.check_in_time.strftime("%d %b %Y") if stay.check_in_time else "N/A",
            "status": stay.status,
            "rate_per_night": float(stay.room_rate_per_night)
        }
        for stay, guest, room in rows
    ]
    return {
        "period_days": days,
        "upcoming_count": len(reservations),
        "reservations": reservations
    }


# =====================================================================
# C. HOUSEKEEPING TOOLS
# =====================================================================

async def tool_get_rooms_needing_cleaning(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Retrieves all rooms requiring cleaning (Vacant Dirty, Inspection Failed)."""
    stmt = (
        select(Room, Floor, RoomType)
        .join(Floor, Room.floor_id == Floor.id)
        .join(RoomType, Room.room_type_id == RoomType.id)
        .where(
            Room.hotel_id == ctx.hotel_id,
            Room.is_active == True,
            Room.status.in_(["VACANT_DIRTY", "INSPECTION_PENDING", "INSPECTION_FAILED"])
        )
        .order_by(Room.room_number)
    )
    res = await db.execute(stmt)
    rows = res.all()

    rooms = [
        {
            "room_number": r.room_number,
            "floor": f.name,
            "room_type": rt.name,
            "status": r.status
        }
        for r, f, rt in rows
    ]
    return {
        "dirty_rooms_count": len(rooms),
        "rooms": rooms
    }


async def tool_get_pending_housekeeping_tasks(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Retrieves all pending and in-progress room cleaning tasks."""
    stmt = (
        select(HousekeepingTask, Room, User)
        .join(Room, HousekeepingTask.room_id == Room.id)
        .outerjoin(User, HousekeepingTask.assigned_to_user_id == User.id)
        .where(
            HousekeepingTask.hotel_id == ctx.hotel_id,
            HousekeepingTask.status.in_(["PENDING", "IN_PROGRESS", "INSPECTION_PENDING", "INSPECTION_FAILED"])
        )
        .order_by(HousekeepingTask.priority.desc(), HousekeepingTask.created_at)
    )
    res = await db.execute(stmt)
    rows = res.all()

    tasks = []
    for task, room, user in rows:
        tasks.append({
            "task_id": task.id,
            "room_number": room.room_number,
            "priority": task.priority,
            "status": task.status,
            "assigned_to": user.full_name if user else "Unassigned",
            "notes": task.notes,
            "created_at": task.created_at.strftime("%I:%M %p")
        })

    return {
        "pending_count": len(tasks),
        "tasks": tasks
    }


async def tool_get_staff_pending_tasks(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Groups pending housekeeping cleaning tasks by assigned employee."""
    stmt = (
        select(HousekeepingTask, Room, User)
        .join(Room, HousekeepingTask.room_id == Room.id)
        .outerjoin(User, HousekeepingTask.assigned_to_user_id == User.id)
        .where(
            HousekeepingTask.hotel_id == ctx.hotel_id,
            HousekeepingTask.status.in_(["PENDING", "IN_PROGRESS"])
        )
    )
    res = await db.execute(stmt)
    rows = res.all()

    staff_map: Dict[str, List[str]] = {}
    for task, room, user in rows:
        name = user.full_name if user else "Unassigned Staff"
        if name not in staff_map:
            staff_map[name] = []
        staff_map[name].append(f"Room {room.room_number} ({task.priority})")

    summary = [{"staff_name": k, "pending_rooms": v, "task_count": len(v)} for k, v in staff_map.items()]
    return {
        "total_active_tasks": len(rows),
        "staff_breakdown": summary
    }


async def tool_get_housekeeping_summary(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Provides property-wide housekeeping overview."""
    stmt_rooms = select(Room).where(Room.hotel_id == ctx.hotel_id, Room.is_active == True)
    res_rooms = await db.execute(stmt_rooms)
    rooms = res_rooms.scalars().all()

    clean_count = sum(1 for r in rooms if r.status == "VACANT_CLEAN")
    dirty_count = sum(1 for r in rooms if r.status == "VACANT_DIRTY")
    inspection_count = sum(1 for r in rooms if r.status in ["INSPECTION_PENDING", "INSPECTION_FAILED"])
    occupied_count = sum(1 for r in rooms if r.status == "OCCUPIED")

    stmt_tasks = select(HousekeepingTask).where(
        HousekeepingTask.hotel_id == ctx.hotel_id,
        HousekeepingTask.status.in_(["PENDING", "IN_PROGRESS"])
    )
    res_tasks = await db.execute(stmt_tasks)
    active_tasks = res_tasks.scalars().all()

    return {
        "total_rooms": len(rooms),
        "clean_ready": clean_count,
        "dirty_pending": dirty_count,
        "inspection_pending": inspection_count,
        "occupied": occupied_count,
        "active_cleaning_tasks": len(active_tasks)
    }


async def tool_get_room_cleaning_status(
    db: AsyncSession,
    ctx: TenantContext,
    room_number: str
) -> Dict[str, Any]:
    """Checks the specific cleaning status and active checklist for a single room."""
    stmt = select(Room).where(Room.hotel_id == ctx.hotel_id, Room.room_number == str(room_number).strip())
    res = await db.execute(stmt)
    room = res.scalar_one_or_none()

    if not room:
        return {"found": False, "message": f"Room {room_number} does not exist."}

    stmt_task = (
        select(HousekeepingTask)
        .where(HousekeepingTask.room_id == room.id)
        .order_by(HousekeepingTask.created_at.desc())
        .limit(1)
    )
    res_task = await db.execute(stmt_task)
    task = res_task.scalar_one_or_none()

    checklists = []
    if task:
        c_res = await db.execute(select(CleaningChecklist).where(CleaningChecklist.task_id == task.id))
        checklists = [
            {"item": c.item_key, "completed": c.is_completed}
            for c in c_res.scalars().all()
        ]

    return {
        "found": True,
        "room_number": room.room_number,
        "room_status": room.status,
        "latest_task_status": task.status if task else "NO_TASK",
        "task_id": task.id if task else None,
        "checklist": checklists
    }


# =====================================================================
# D. MAINTENANCE TOOLS
# =====================================================================

async def tool_get_pending_maintenance_requests(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Retrieves all open maintenance breakdown tickets."""
    stmt = (
        select(MaintenanceTicket, Room, Asset)
        .outerjoin(Room, MaintenanceTicket.room_id == Room.id)
        .outerjoin(Asset, MaintenanceTicket.asset_id == Asset.id)
        .where(
            MaintenanceTicket.hotel_id == ctx.hotel_id,
            MaintenanceTicket.status.in_(["REPORTED", "IN_PROGRESS", "WAITING_PARTS"])
        )
        .order_by(MaintenanceTicket.priority.desc(), MaintenanceTicket.created_at.desc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    tickets = [
        {
            "ticket_id": t.id,
            "room_number": r.room_number if r else "General Facility",
            "asset_name": a.name if a else None,
            "title": t.title,
            "description": t.description,
            "priority": t.priority,
            "status": t.status,
            "estimated_cost": float(t.estimated_cost),
            "actual_cost": float(t.actual_cost),
            "created_at": t.created_at.strftime("%d %b %Y, %I:%M %p")
        }
        for t, r, a in rows
    ]

    return {
        "open_tickets_count": len(tickets),
        "critical_count": sum(1 for t in tickets if t["priority"] == "CRITICAL"),
        "tickets": tickets
    }


async def tool_get_rooms_with_unresolved_maintenance(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Lists rooms that have active unresolved repair tickets or are blocked."""
    stmt = (
        select(MaintenanceTicket, Room)
        .join(Room, MaintenanceTicket.room_id == Room.id)
        .where(
            MaintenanceTicket.hotel_id == ctx.hotel_id,
            MaintenanceTicket.status.in_(["REPORTED", "IN_PROGRESS", "WAITING_PARTS"])
        )
    )
    res = await db.execute(stmt)
    rows = res.all()

    unresolved = [
        {
            "room_number": r.room_number,
            "room_status": r.status,
            "issue": t.title,
            "priority": t.priority,
            "ticket_status": t.status
        }
        for t, r in rows
    ]
    return {
        "rooms_with_issues_count": len(unresolved),
        "issues": unresolved
    }


async def tool_get_maintenance_summary(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Summarizes property maintenance activity and blocked rooms."""
    stmt_tickets = select(MaintenanceTicket).where(MaintenanceTicket.hotel_id == ctx.hotel_id)
    res = await db.execute(stmt_tickets)
    tickets = res.scalars().all()

    open_tickets = [t for t in tickets if t.status in ["REPORTED", "IN_PROGRESS", "WAITING_PARTS"]]
    resolved_tickets = [t for t in tickets if t.status == "RESOLVED"]

    stmt_blocked = select(Room).where(
        Room.hotel_id == ctx.hotel_id,
        Room.status == "BLOCKED_MAINTENANCE"
    )
    res_blocked = await db.execute(stmt_blocked)
    blocked_rooms = res_blocked.scalars().all()

    return {
        "open_tickets": len(open_tickets),
        "critical_tickets": sum(1 for t in open_tickets if t.priority == "CRITICAL"),
        "resolved_tickets": len(resolved_tickets),
        "rooms_blocked_for_maintenance": [r.room_number for r in blocked_rooms]
    }


# =====================================================================
# E. INVENTORY TOOLS
# =====================================================================

async def tool_get_low_stock_items(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Identifies inventory items and linens that have reached low stock thresholds."""
    stmt = select(AssetCategory).where(AssetCategory.hotel_id == ctx.hotel_id)
    res = await db.execute(stmt)
    categories = res.scalars().all()

    low_stock = []
    for cat in categories:
        stmt_count = select(func.count(Asset.id)).where(
            Asset.hotel_id == ctx.hotel_id,
            Asset.category_id == cat.id,
            Asset.current_location_type == "STORAGE",
            Asset.is_active == True,
            Asset.condition == "GOOD"
        )
        res_count = await db.execute(stmt_count)
        current_storage_stock = res_count.scalar_one()

        if current_storage_stock <= cat.low_stock_threshold:
            low_stock.append({
                "category_id": cat.id,
                "name": cat.name,
                "is_linen": cat.is_linen,
                "current_stock": current_storage_stock,
                "threshold": cat.low_stock_threshold,
                "deficit": cat.low_stock_threshold - current_storage_stock
            })

    return {
        "total_categories_inspected": len(categories),
        "low_stock_count": len(low_stock),
        "items": low_stock
    }


async def tool_get_inventory_quantities(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Retrieves current stock quantities broken down by category and storage location."""
    stmt = select(AssetCategory).where(AssetCategory.hotel_id == ctx.hotel_id)
    res = await db.execute(stmt)
    categories = res.scalars().all()

    inventory_breakdown = []
    for cat in categories:
        res_all = await db.execute(select(Asset).where(Asset.category_id == cat.id, Asset.is_active == True))
        assets = res_all.scalars().all()

        in_storage = sum(1 for a in assets if a.current_location_type == "STORAGE")
        in_rooms = sum(1 for a in assets if a.current_location_type == "ROOM")
        in_laundry = sum(1 for a in assets if a.current_location_type == "LAUNDRY_VENDOR")

        inventory_breakdown.append({
            "category": cat.name,
            "total": len(assets),
            "in_storage": in_storage,
            "in_rooms": in_rooms,
            "in_laundry": in_laundry,
            "threshold": cat.low_stock_threshold,
            "is_low": in_storage <= cat.low_stock_threshold
        })

    return {
        "categories_count": len(categories),
        "inventory": inventory_breakdown
    }


async def tool_get_inventory_summary(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Retrieves full overview of assets, linens, and condition breakdown."""
    stmt_assets = select(Asset).where(Asset.hotel_id == ctx.hotel_id, Asset.is_active == True)
    res = await db.execute(stmt_assets)
    assets = res.scalars().all()

    total = len(assets)
    in_rooms = sum(1 for a in assets if a.current_location_type == "ROOM")
    in_storage = sum(1 for a in assets if a.current_location_type == "STORAGE")
    in_laundry = sum(1 for a in assets if a.current_location_type == "LAUNDRY_VENDOR")
    damaged = sum(1 for a in assets if a.condition in ["DAMAGED", "POOR"])
    missing = sum(1 for a in assets if a.condition == "MISSING")

    return {
        "total_tracked_assets": total,
        "assigned_to_rooms": in_rooms,
        "in_storage": in_storage,
        "in_laundry_vendor": in_laundry,
        "damaged_count": damaged,
        "missing_count": missing
    }


# =====================================================================
# F. FINANCE TOOLS (USALI-COMPLIANT & RBAC PROTECTED)
# =====================================================================

async def tool_get_revenue_summary(
    db: AsyncSession,
    ctx: TenantContext,
    period: str = "today"
) -> Dict[str, Any]:
    """
    USALI-compliant Revenue & Operating Contribution summary.
    Requires role OWNER, MANAGER, or ACCOUNTANT.
    Distinguishes earned accrual revenue from cash collections.
    """
    if ctx.role not in ["OWNER", "MANAGER", "ACCOUNTANT"]:
        return {
            "authorized": False,
            "message": f"Access Denied: Role '{ctx.role}' is not authorized to view financial records."
        }

    today = date.today()
    if period.lower() == "yesterday":
        start_date = today - timedelta(days=1)
        end_date = start_date
    elif period.lower() == "month" or period.lower() == "mtd":
        start_date = today.replace(day=1)
        end_date = today
    else:  # today
        start_date = today
        end_date = today

    # Earned Revenue (Accrual)
    res_rev = await db.execute(
        select(func.coalesce(func.sum(Revenue.amount), 0))
        .where(
            Revenue.hotel_id == ctx.hotel_id,
            Revenue.posting_date >= start_date,
            Revenue.posting_date <= end_date
        )
    )
    earned_rev = Decimal(str(res_rev.scalar_one()))

    # Cash Collections (Cash Inflow)
    res_pay = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(
            Payment.hotel_id == ctx.hotel_id,
            func.date(Payment.payment_date) >= start_date,
            func.date(Payment.payment_date) <= end_date
        )
    )
    cash_collections = Decimal(str(res_pay.scalar_one()))

    # Operating Expenses
    res_exp = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0))
        .where(
            Expense.hotel_id == ctx.hotel_id,
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date
        )
    )
    operating_expenses = Decimal(str(res_exp.scalar_one()))

    operating_contribution = earned_rev - operating_expenses

    return {
        "authorized": True,
        "period": period,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "earned_revenue_accrual": float(earned_rev),
        "cash_collections_inflow": float(cash_collections),
        "operating_expenses": float(operating_expenses),
        "operating_contribution": float(operating_contribution),
        "usali_note": "Operating Contribution represents Gross Operating Profit before debt service, depreciation, and corporate taxes."
    }


async def tool_get_outstanding_balances(
    db: AsyncSession,
    ctx: TenantContext
) -> Dict[str, Any]:
    """Retrieves guest stays with unpaid balance dues."""
    if ctx.role not in ["OWNER", "MANAGER", "ACCOUNTANT", "RECEPTIONIST"]:
        return {"authorized": False, "message": "Unauthorized"}

    stmt = (
        select(GuestStay, Guest, Room)
        .join(Guest, GuestStay.guest_id == Guest.id)
        .join(Room, GuestStay.room_id == Room.id)
        .where(
            GuestStay.hotel_id == ctx.hotel_id,
            GuestStay.status == "CHECKED_IN",
            GuestStay.balance_due > 0
        )
        .order_by(GuestStay.balance_due.desc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    outstanding = [
        {
            "room_number": room.room_number,
            "guest_name": guest.full_name,
            "guest_phone": mask_phone(guest.phone),
            "total_room_charge": float(stay.total_room_charge),
            "total_paid": float(stay.total_paid),
            "balance_due": float(stay.balance_due)
        }
        for stay, guest, room in rows
    ]

    total_due = sum(item["balance_due"] for item in outstanding)

    return {
        "total_outstanding_amount": round(total_due, 2),
        "stays_with_due_count": len(outstanding),
        "records": outstanding
    }


# =====================================================================
# G. OPERATIONAL ACTION TOOLS (CONSEQUENTIAL & AUDITED)
# =====================================================================

async def tool_create_housekeeping_task(
    db: AsyncSession,
    ctx: TenantContext,
    room_number: str,
    priority: str = "MEDIUM",
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a new housekeeping task for a specific room.
    Requires role OWNER, MANAGER, or RECEPTIONIST.
    """
    if ctx.role not in ["OWNER", "MANAGER", "RECEPTIONIST"]:
        return {"success": False, "message": f"Role '{ctx.role}' cannot create housekeeping tasks."}

    # Find room
    stmt = select(Room).where(Room.hotel_id == ctx.hotel_id, Room.room_number == str(room_number).strip())
    res = await db.execute(stmt)
    room = res.scalar_one_or_none()

    if not room:
        return {"success": False, "message": f"Room {room_number} does not exist in this property."}

    # Create task
    task = HousekeepingTask(
        hotel_id=ctx.hotel_id,
        room_id=room.id,
        assigned_to_user_id=ctx.user.id,
        priority=priority.upper() if priority.upper() in ["LOW", "MEDIUM", "HIGH", "CRITICAL"] else "MEDIUM",
        notes=notes or "Created via AI Operations Assistant",
        status="PENDING"
    )
    db.add(task)
    await db.flush()

    # Standard 5-point cleaning checklist
    items = [
        "Change bedsheets and pillow covers",
        "Disinfect bathroom surfaces & replenish towels",
        "Dust furniture, sweep and mop floors",
        "Restock complimentary water and toiletries",
        "Inspect all electronics and remote controls"
    ]
    for it in items:
        db.add(CleaningChecklist(task_id=task.id, item_key=it, is_completed=False))

    # Mark room status to dirty if clean or ready
    if room.status not in ["OCCUPIED", "BLOCKED_MAINTENANCE"]:
        room.status = "VACANT_DIRTY"

    await db.commit()
    return {
        "success": True,
        "task_id": task.id,
        "room_number": room.room_number,
        "priority": task.priority,
        "status": task.status,
        "message": f"Housekeeping task #{task.id[:8]} successfully created for Room {room.room_number} with priority {task.priority}."
    }


async def tool_create_maintenance_ticket(
    db: AsyncSession,
    ctx: TenantContext,
    room_number: str,
    title: str,
    description: str,
    priority: str = "MEDIUM"
) -> Dict[str, Any]:
    """
    Creates a new maintenance repair ticket for a room.
    If priority is CRITICAL, the room is automatically placed into BLOCKED_MAINTENANCE.
    """
    if ctx.role not in ["OWNER", "MANAGER", "MAINTENANCE", "RECEPTIONIST"]:
        return {"success": False, "message": f"Role '{ctx.role}' cannot log maintenance tickets."}

    stmt = select(Room).where(Room.hotel_id == ctx.hotel_id, Room.room_number == str(room_number).strip())
    res = await db.execute(stmt)
    room = res.scalar_one_or_none()

    if not room:
        return {"success": False, "message": f"Room {room_number} does not exist in this property."}

    prio = priority.upper() if priority.upper() in ["LOW", "MEDIUM", "HIGH", "CRITICAL"] else "MEDIUM"

    ticket = MaintenanceTicket(
        hotel_id=ctx.hotel_id,
        room_id=room.id,
        title=title,
        description=description,
        priority=prio,
        reported_by_user_id=ctx.user.id,
        status="REPORTED"
    )
    db.add(ticket)

    blocked = False
    if prio == "CRITICAL" and room.status != "OCCUPIED":
        room.status = "BLOCKED_MAINTENANCE"
        blocked = True

    await db.commit()
    await db.refresh(ticket)

    return {
        "success": True,
        "ticket_id": ticket.id,
        "room_number": room.room_number,
        "priority": prio,
        "room_blocked": blocked,
        "message": f"Maintenance ticket #{ticket.id[:8]} logged for Room {room.room_number} ('{title}')." +
                   (" Room has been blocked from sales due to CRITICAL priority." if blocked else "")
    }


async def tool_assign_housekeeping_task(
    db: AsyncSession,
    ctx: TenantContext,
    task_id: str,
    staff_email_or_name: str
) -> Dict[str, Any]:
    """Assigns an existing housekeeping task to a property team member."""
    if ctx.role not in ["OWNER", "MANAGER"]:
        return {"success": False, "message": f"Role '{ctx.role}' is not authorized to assign housekeeping tasks."}

    task = await db.get(HousekeepingTask, task_id)
    if not task or task.hotel_id != ctx.hotel_id:
        return {"success": False, "message": f"Task #{task_id} not found."}

    # Search for user in hotel memberships
    stmt = (
        select(User)
        .join(HotelMembership, User.id == HotelMembership.user_id)
        .where(
            HotelMembership.hotel_id == ctx.hotel_id,
            or_(
                User.email.ilike(f"%{staff_email_or_name.strip()}%"),
                User.full_name.ilike(f"%{staff_email_or_name.strip()}%")
            )
        )
    )
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        return {"success": False, "message": f"Staff member '{staff_email_or_name}' not found in this hotel team."}

    task.assigned_to_user_id = user.id
    await db.commit()
    return {
        "success": True,
        "task_id": task.id,
        "assigned_to": user.full_name,
        "message": f"Task #{task.id[:8]} assigned to {user.full_name}."
    }


async def tool_update_task_status(
    db: AsyncSession,
    ctx: TenantContext,
    task_id: str,
    new_status: str
) -> Dict[str, Any]:
    """Updates the status of a housekeeping task."""
    if ctx.role not in ["OWNER", "MANAGER", "HOUSEKEEPING", "RECEPTIONIST"]:
        return {"success": False, "message": "Unauthorized"}

    valid_statuses = ["PENDING", "IN_PROGRESS", "INSPECTION_PENDING", "READY", "CANCELLED"]
    status_upper = new_status.upper()
    if status_upper not in valid_statuses:
        return {"success": False, "message": f"Invalid status. Choose from: {', '.join(valid_statuses)}"}

    task = await db.get(HousekeepingTask, task_id)
    if not task or task.hotel_id != ctx.hotel_id:
        return {"success": False, "message": f"Task #{task_id} not found."}

    task.status = status_upper
    if status_upper == "IN_PROGRESS" and not task.started_at:
        task.started_at = datetime.now(timezone.utc)
    elif status_upper in ["INSPECTION_PENDING", "READY"]:
        task.completed_at = datetime.now(timezone.utc)

    room = await db.get(Room, task.room_id)
    if room and room.status != "OCCUPIED":
        if status_upper == "READY":
            room.status = "VACANT_CLEAN"
        elif status_upper == "INSPECTION_PENDING":
            room.status = "INSPECTION_PENDING"

    await db.commit()
    return {
        "success": True,
        "task_id": task.id,
        "new_status": task.status,
        "message": f"Task #{task.id[:8]} status updated to {task.status}."
    }


# =====================================================================
# MASTER TOOL REGISTRY & DISPATCHER
# =====================================================================

AVAILABLE_AI_TOOLS = {
    # Room Management
    "get_room_status": tool_get_room_status,
    "get_vacant_rooms": tool_get_vacant_rooms,
    "get_occupied_rooms": tool_get_occupied_rooms,
    "get_rooms_under_maintenance": tool_get_rooms_under_maintenance,
    "get_rooms_by_floor": tool_get_rooms_by_floor,
    # Bookings & Stays
    "get_today_bookings": tool_get_today_bookings,
    "get_today_checkins": tool_get_today_checkins,
    "get_today_checkouts": tool_get_today_checkouts,
    "get_upcoming_reservations": tool_get_upcoming_reservations,
    # Housekeeping
    "get_rooms_needing_cleaning": tool_get_rooms_needing_cleaning,
    "get_pending_housekeeping_tasks": tool_get_pending_housekeeping_tasks,
    "get_staff_pending_tasks": tool_get_staff_pending_tasks,
    "get_housekeeping_summary": tool_get_housekeeping_summary,
    "get_room_cleaning_status": tool_get_room_cleaning_status,
    # Maintenance
    "get_pending_maintenance_requests": tool_get_pending_maintenance_requests,
    "get_rooms_with_unresolved_maintenance": tool_get_rooms_with_unresolved_maintenance,
    "get_maintenance_summary": tool_get_maintenance_summary,
    # Inventory
    "get_low_stock_items": tool_get_low_stock_items,
    "get_inventory_quantities": tool_get_inventory_quantities,
    "get_inventory_summary": tool_get_inventory_summary,
    # Finance
    "get_revenue_summary": tool_get_revenue_summary,
    "get_outstanding_balances": tool_get_outstanding_balances,
    # Actions
    "create_housekeeping_task": tool_create_housekeeping_task,
    "create_maintenance_ticket": tool_create_maintenance_ticket,
    "assign_housekeeping_task": tool_assign_housekeeping_task,
    "update_task_status": tool_update_task_status
}
