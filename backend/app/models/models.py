import uuid
from datetime import datetime, timezone, date, time
from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, Date, Time, DateTime, 
    ForeignKey, Text, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from app.models.base import TimeStampedBase, generate_uuid
from app.core.database import Base

# -------------------------------------------------------------
# 1. PLATFORM & MULTI-TENANCY
# -------------------------------------------------------------

class User(TimeStampedBase):
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(150), nullable=False)
    phone_number = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_platform_admin = Column(Boolean, default=False, nullable=False)
    
    memberships = relationship("HotelMembership", back_populates="user", cascade="all, delete-orphan")


class Hotel(TimeStampedBase):
    __tablename__ = "hotels"
    
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    address = Column(Text, nullable=False)
    city = Column(String(100), default="Varanasi", nullable=False)
    state = Column(String(100), default="Uttar Pradesh", nullable=False)
    country = Column(String(100), default="India", nullable=False)
    postal_code = Column(String(20), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(255), nullable=False)
    timezone = Column(String(50), default="Asia/Kolkata", nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    check_in_time = Column(String(10), default="12:00", nullable=False)
    check_out_time = Column(String(10), default="11:00", nullable=False)
    reporting_time = Column(String(10), default="23:59", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    memberships = relationship("HotelMembership", back_populates="hotel", cascade="all, delete-orphan")
    floors = relationship("Floor", back_populates="hotel", cascade="all, delete-orphan")
    room_types = relationship("RoomType", back_populates="hotel", cascade="all, delete-orphan")
    rooms = relationship("Room", back_populates="hotel", cascade="all, delete-orphan")


class HotelMembership(TimeStampedBase):
    __tablename__ = "hotel_memberships"
    
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(30), nullable=False)  # OWNER, MANAGER, RECEPTIONIST, HOUSEKEEPING, MAINTENANCE, ACCOUNTANT
    is_active = Column(Boolean, default=True, nullable=False)
    
    user = relationship("User", back_populates="memberships")
    hotel = relationship("Hotel", back_populates="memberships")
    
    __table_args__ = (
        UniqueConstraint("user_id", "hotel_id", name="uq_user_hotel_membership"),
    )


# -------------------------------------------------------------
# 2. HOTEL STRUCTURE: FLOORS, ROOM TYPES, ROOMS
# -------------------------------------------------------------

class Floor(Base):
    __tablename__ = "floors"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    floor_number = Column(Integer, nullable=False)
    name = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    hotel = relationship("Hotel", back_populates="floors")
    rooms = relationship("Room", back_populates="floor")
    
    __table_args__ = (
        UniqueConstraint("hotel_id", "floor_number", name="uq_hotel_floor_number"),
    )


class RoomType(TimeStampedBase):
    __tablename__ = "room_types"
    
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # Deluxe, Executive, Suite
    base_price = Column(Numeric(12, 2), nullable=False)
    max_capacity = Column(Integer, default=2, nullable=False)
    amenities = Column(JSON, default=list, nullable=False)
    description = Column(Text, nullable=True)
    
    hotel = relationship("Hotel", back_populates="room_types")
    rooms = relationship("Room", back_populates="room_type")
    
    __table_args__ = (
        UniqueConstraint("hotel_id", "name", name="uq_hotel_room_type_name"),
    )


class Room(TimeStampedBase):
    __tablename__ = "rooms"
    
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    floor_id = Column(String(36), ForeignKey("floors.id", ondelete="RESTRICT"), nullable=False, index=True)
    room_type_id = Column(String(36), ForeignKey("room_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    room_number = Column(String(20), nullable=False)
    status = Column(String(30), default="VACANT_CLEAN", nullable=False, index=True)
    # VACANT_CLEAN, VACANT_DIRTY, OCCUPIED, INSPECTION_PENDING, INSPECTION_FAILED, BLOCKED_MAINTENANCE
    is_active = Column(Boolean, default=True, nullable=False)
    
    hotel = relationship("Hotel", back_populates="rooms")
    floor = relationship("Floor", back_populates="rooms")
    room_type = relationship("RoomType", back_populates="rooms")
    assets = relationship("Asset", back_populates="current_room")
    stays = relationship("GuestStay", back_populates="room")
    housekeeping_tasks = relationship("HousekeepingTask", back_populates="room")
    maintenance_tickets = relationship("MaintenanceTicket", back_populates="room")
    
    __table_args__ = (
        UniqueConstraint("hotel_id", "room_number", name="uq_hotel_room_number"),
    )


# -------------------------------------------------------------
# 3. ASSET & INVENTORY LEDGER
# -------------------------------------------------------------

class AssetCategory(Base):
    __tablename__ = "asset_categories"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    is_linen = Column(Boolean, default=False, nullable=False)
    is_consumable = Column(Boolean, default=False, nullable=False)
    low_stock_threshold = Column(Integer, default=5, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    assets = relationship("Asset", back_populates="category")
    
    __table_args__ = (
        UniqueConstraint("hotel_id", "name", name="uq_hotel_asset_category_name"),
    )


class Asset(TimeStampedBase):
    __tablename__ = "assets"
    
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(String(36), ForeignKey("asset_categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    asset_tag = Column(String(50), nullable=True)
    qr_code_identifier = Column(String(100), unique=True, index=True, nullable=True)
    current_location_type = Column(String(30), default="STORAGE", nullable=False)
    # ROOM, STORAGE, LAUNDRY, VENDOR, SCRAPPED
    current_room_id = Column(String(36), ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, index=True)
    condition = Column(String(20), default="GOOD", nullable=False)
    # EXCELLENT, GOOD, FAIR, DAMAGED, MISSING
    purchase_price = Column(Numeric(12, 2), default=0.00, nullable=False)
    purchase_date = Column(Date, nullable=True)
    warranty_expiry = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    category = relationship("AssetCategory", back_populates="assets")
    current_room = relationship("Room", back_populates="assets")
    transactions = relationship("InventoryTransaction", back_populates="asset")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True)
    category_id = Column(String(36), ForeignKey("asset_categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    transaction_type = Column(String(30), nullable=False)
    # PURCHASE, ASSIGN_ROOM, RETURN_STORAGE, DISPATCH_LAUNDRY, RECEIVE_LAUNDRY, TRANSFER, MARK_DAMAGED, MARK_MISSING, DISCARD
    quantity = Column(Integer, nullable=False)
    from_location = Column(String(50), nullable=False)
    to_location = Column(String(50), nullable=False)
    unit_cost = Column(Numeric(12, 2), default=0.00, nullable=False)
    reference_id = Column(String(36), nullable=True)
    notes = Column(Text, nullable=True)
    performed_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    asset = relationship("Asset", back_populates="transactions")
    performed_by = relationship("User")


class InventoryAudit(Base):
    __tablename__ = "inventory_audits"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    room_id = Column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=True, index=True)
    audit_date = Column(Date, default=date.today, nullable=False)
    conducted_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status = Column(String(30), default="IN_PROGRESS", nullable=False) # IN_PROGRESS, COMPLETED, DISCREPANCY_FLAGGED
    discrepancy_count = Column(Integer, default=0, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    items = relationship("InventoryAuditItem", back_populates="audit", cascade="all, delete-orphan")


class InventoryAuditItem(Base):
    __tablename__ = "inventory_audit_items"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    audit_id = Column(String(36), ForeignKey("inventory_audits.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False)
    expected_status = Column(String(30), nullable=False)
    actual_status = Column(String(30), nullable=False)
    discrepancy_type = Column(String(30), nullable=True) # MISSING, DAMAGED, UNREGISTERED_FOUND, NONE
    notes = Column(Text, nullable=True)
    
    audit = relationship("InventoryAudit", back_populates="items")
    asset = relationship("Asset")


# -------------------------------------------------------------
# 4. HOUSEKEEPING, MAINTENANCE & LAUNDRY
# -------------------------------------------------------------

class HousekeepingTask(Base):
    __tablename__ = "housekeeping_tasks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    room_id = Column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_to_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), default="PENDING", nullable=False, index=True)
    # PENDING, IN_PROGRESS, CLEANED, INSPECTION_PENDING, INSPECTION_FAILED, READY
    priority = Column(String(20), default="NORMAL", nullable=False) # LOW, NORMAL, HIGH, URGENT
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    room = relationship("Room", back_populates="housekeeping_tasks")
    assigned_to = relationship("User")
    checklists = relationship("CleaningChecklist", back_populates="task", cascade="all, delete-orphan")
    inspections = relationship("RoomInspection", back_populates="task", cascade="all, delete-orphan")


class CleaningChecklist(Base):
    __tablename__ = "cleaning_checklists"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("housekeeping_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    item_key = Column(String(100), nullable=False)
    is_completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    task = relationship("HousekeepingTask", back_populates="checklists")


class RoomInspection(Base):
    __tablename__ = "room_inspections"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(String(36), ForeignKey("housekeeping_tasks.id", ondelete="CASCADE"), nullable=False)
    room_id = Column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    inspector_user_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status = Column(String(20), nullable=False) # PASSED, FAILED
    rejection_reason = Column(Text, nullable=True)
    inspected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    task = relationship("HousekeepingTask", back_populates="inspections")
    inspector = relationship("User")


class MaintenanceTicket(TimeStampedBase):
    __tablename__ = "maintenance_tickets"
    
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    room_id = Column(String(36), ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(20), default="MEDIUM", nullable=False) # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String(20), default="REPORTED", nullable=False, index=True)
    # REPORTED, IN_PROGRESS, WAITING_PARTS, RESOLVED, CANCELLED
    reported_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    assigned_technician_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    photo_urls = Column(JSON, default=list, nullable=False)
    estimated_cost = Column(Numeric(12, 2), default=0.00, nullable=False)
    actual_cost = Column(Numeric(12, 2), default=0.00, nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    room = relationship("Room", back_populates="maintenance_tickets")
    asset = relationship("Asset")
    reported_by = relationship("User", foreign_keys=[reported_by_user_id])
    assigned_technician = relationship("User", foreign_keys=[assigned_technician_id])
    updates = relationship("MaintenanceUpdate", back_populates="ticket", cascade="all, delete-orphan")


class MaintenanceUpdate(Base):
    __tablename__ = "maintenance_updates"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    ticket_id = Column(String(36), ForeignKey("maintenance_tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    message = Column(Text, nullable=False)
    status_change = Column(String(20), nullable=True)
    additional_cost = Column(Numeric(12, 2), default=0.00, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    ticket = relationship("MaintenanceTicket", back_populates="updates")
    user = relationship("User")


class LaundryVendor(Base):
    __tablename__ = "laundry_vendors"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    contact_person = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=False)
    rate_per_kg = Column(Numeric(8, 2), nullable=True)
    rate_per_piece = Column(Numeric(8, 2), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class LaundryBatch(Base):
    __tablename__ = "laundry_batches"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id = Column(String(36), ForeignKey("laundry_vendors.id", ondelete="RESTRICT"), nullable=False)
    dispatched_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    dispatch_date = Column(Date, default=date.today, nullable=False)
    expected_return_date = Column(Date, nullable=True)
    actual_return_date = Column(Date, nullable=True)
    status = Column(String(20), default="DISPATCHED", nullable=False)
    # DISPATCHED, PARTIALLY_RECEIVED, RECEIVED, RECONCILED
    total_items_sent = Column(Integer, nullable=False)
    total_items_received = Column(Integer, default=0, nullable=False)
    damaged_items_count = Column(Integer, default=0, nullable=False)
    missing_items_count = Column(Integer, default=0, nullable=False)
    total_cost = Column(Numeric(12, 2), default=0.00, nullable=False)
    is_paid = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    vendor = relationship("LaundryVendor")
    items = relationship("LaundryItem", back_populates="batch", cascade="all, delete-orphan")


class LaundryItem(Base):
    __tablename__ = "laundry_items"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    batch_id = Column(String(36), ForeignKey("laundry_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(String(36), ForeignKey("asset_categories.id", ondelete="RESTRICT"), nullable=False)
    quantity_sent = Column(Integer, nullable=False)
    quantity_received = Column(Integer, default=0, nullable=False)
    damaged_count = Column(Integer, default=0, nullable=False)
    missing_count = Column(Integer, default=0, nullable=False)
    unit_cost = Column(Numeric(8, 2), default=0.00, nullable=False)
    
    batch = relationship("LaundryBatch", back_populates="items")
    category = relationship("AssetCategory")


# -------------------------------------------------------------
# 5. EMPLOYEES & AUDIT LOGS
# -------------------------------------------------------------

class Employee(TimeStampedBase):
    __tablename__ = "employees"
    
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    department = Column(String(50), nullable=False) # FRONT_DESK, HOUSEKEEPING, MAINTENANCE, FINANCE, MANAGEMENT
    employee_code = Column(String(50), nullable=False)
    date_of_joining = Column(Date, default=date.today, nullable=False)
    salary_monthly = Column(Numeric(12, 2), default=0.00, nullable=False)
    shift = Column(String(20), default="MORNING", nullable=False) # MORNING, EVENING, NIGHT, ROTATIONAL
    
    user = relationship("User")
    
    __table_args__ = (
        UniqueConstraint("hotel_id", "employee_code", name="uq_hotel_employee_code"),
    )


class Attendance(Base):
    __tablename__ = "attendance"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, default=date.today, nullable=False)
    check_in_time = Column(Time, nullable=True)
    check_out_time = Column(Time, nullable=True)
    status = Column(String(20), default="PRESENT", nullable=False) # PRESENT, ABSENT, HALF_DAY, LEAVE
    
    employee = relationship("Employee")
    
    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_employee_attendance_date"),
    )


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action_type = Column(String(50), nullable=False) # CREATE, UPDATE, DELETE, STATUS_CHANGE, CHECK_IN, CHECK_OUT, AUDIT
    entity_type = Column(String(50), nullable=False) # ROOM, ASSET, STAY, EXPENSE, TICKET, LAUNDRY
    entity_id = Column(String(36), nullable=False)
    details = Column(JSON, default=dict, nullable=False)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    user = relationship("User")


# -------------------------------------------------------------
# 6. GUESTS & DIGITAL CHECK-IN
# -------------------------------------------------------------

class Guest(TimeStampedBase):
    __tablename__ = "guests"
    
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=False, index=True)
    id_type = Column(String(30), nullable=True) # PASSPORT, DRIVING_LICENSE, VOTER_ID, AADHAAR_MASKED
    id_number_masked = Column(String(50), nullable=True)
    nationality = Column(String(50), default="Indian", nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    is_blacklisted = Column(Boolean, default=False, nullable=False)
    
    stays = relationship("GuestStay", back_populates="guest")


class GuestStay(TimeStampedBase):
    __tablename__ = "guest_stays"
    
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    guest_id = Column(String(36), ForeignKey("guests.id", ondelete="RESTRICT"), nullable=False, index=True)
    room_id = Column(String(36), ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False, index=True)
    check_in_time = Column(DateTime(timezone=True), nullable=False)
    expected_check_out_time = Column(DateTime(timezone=True), nullable=False)
    actual_check_out_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="RESERVED", nullable=False, index=True)
    # RESERVED, CHECKED_IN, CHECKED_OUT, CANCELLED, NO_SHOW
    adult_count = Column(Integer, default=1, nullable=False)
    child_count = Column(Integer, default=0, nullable=False)
    room_rate_per_night = Column(Numeric(12, 2), nullable=False)
    total_room_charge = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_tax_charge = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_additional_charge = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_paid = Column(Numeric(12, 2), default=0.00, nullable=False)
    balance_due = Column(Numeric(12, 2), default=0.00, nullable=False)
    registration_token = Column(String(36), default=generate_uuid, unique=True, index=True, nullable=False)
    
    guest = relationship("Guest", back_populates="stays")
    room = relationship("Room", back_populates="stays")
    revenues = relationship("Revenue", back_populates="stay")
    payments = relationship("Payment", back_populates="stay")
    requests = relationship("GuestRequest", back_populates="stay", cascade="all, delete-orphan")


class GuestDocument(Base):
    __tablename__ = "guest_documents"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    guest_id = Column(String(36), ForeignKey("guests.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type = Column(String(30), nullable=False)
    secure_storage_path = Column(Text, nullable=False)
    verified_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    auto_purge_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class GuestRequest(Base):
    __tablename__ = "guest_requests"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    stay_id = Column(String(36), ForeignKey("guest_stays.id", ondelete="CASCADE"), nullable=False, index=True)
    request_type = Column(String(50), nullable=False) # EXTRA_LINEN, TOWELS, WATER, ROOM_CLEANING, MAINTENANCE
    details = Column(Text, nullable=True)
    status = Column(String(20), default="PENDING", nullable=False) # PENDING, ACKNOWLEDGED, IN_PROGRESS, COMPLETED
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    stay = relationship("GuestStay", back_populates="requests")


# -------------------------------------------------------------
# 7. FINANCIAL MANAGEMENT & ROOM PROFITABILITY
# -------------------------------------------------------------

class ExpenseCategory(Base):
    __tablename__ = "expense_categories"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    is_direct_room_expense = Column(Boolean, default=False, nullable=False)
    allocation_basis = Column(String(30), default="EQUAL_PER_ROOM", nullable=False)
    # DIRECT, EQUAL_PER_ROOM, OCCUPIED_ROOM_NIGHTS, ROOM_SQFT
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        UniqueConstraint("hotel_id", "name", name="uq_hotel_expense_category_name"),
    )


class Expense(TimeStampedBase):
    __tablename__ = "expenses"
    
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(String(36), ForeignKey("expense_categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    room_id = Column(String(36), ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    expense_date = Column(Date, default=date.today, nullable=False, index=True)
    payment_method = Column(String(30), nullable=False) # CASH, UPI, NEFT_RTGS, CARD, CREDIT_VENDOR
    invoice_url = Column(Text, nullable=True)
    description = Column(Text, nullable=False)
    is_allocated = Column(Boolean, default=False, nullable=False)
    approved_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    category = relationship("ExpenseCategory")
    room = relationship("Room")
    approved_by = relationship("User")


class Revenue(Base):
    __tablename__ = "revenues"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    stay_id = Column(String(36), ForeignKey("guest_stays.id", ondelete="SET NULL"), nullable=True, index=True)
    room_id = Column(String(36), ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False, index=True)
    revenue_type = Column(String(30), nullable=False) # ROOM_TARIFF, EXTRA_BED, LAUNDRY_SERVICE, DAMAGE_FEE, LATE_CHECKOUT, MISC
    amount = Column(Numeric(12, 2), nullable=False)
    tax_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    posting_date = Column(Date, default=date.today, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    stay = relationship("GuestStay", back_populates="revenues")
    room = relationship("Room")


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    stay_id = Column(String(36), ForeignKey("guest_stays.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_mode = Column(String(30), nullable=False) # CASH, UPI_QR, CREDIT_DEBIT_CARD, BANK_TRANSFER
    transaction_reference = Column(String(100), nullable=True)
    collected_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    payment_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    stay = relationship("GuestStay", back_populates="payments")
    collected_by = relationship("User")


class Refund(Base):
    __tablename__ = "refunds"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    stay_id = Column(String(36), ForeignKey("guest_stays.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    reason = Column(Text, nullable=False)
    approved_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    refund_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Budget(Base):
    __tablename__ = "budgets"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(String(36), ForeignKey("expense_categories.id", ondelete="CASCADE"), nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    budgeted_amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    category = relationship("ExpenseCategory")
    
    __table_args__ = (
        UniqueConstraint("hotel_id", "category_id", "month", "year", name="uq_hotel_budget_category_month_year"),
    )


class RoomMonthlyContribution(Base):
    __tablename__ = "room_monthly_contributions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    room_id = Column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    available_room_nights = Column(Integer, default=0, nullable=False)
    occupied_room_nights = Column(Integer, default=0, nullable=False)
    total_room_revenue = Column(Numeric(12, 2), default=0.00, nullable=False)
    direct_maintenance_expense = Column(Numeric(12, 2), default=0.00, nullable=False)
    allocated_operating_expense = Column(Numeric(12, 2), default=0.00, nullable=False)
    operating_contribution = Column(Numeric(12, 2), default=0.00, nullable=False)
    adr = Column(Numeric(12, 2), default=0.00, nullable=False)
    revpar = Column(Numeric(12, 2), default=0.00, nullable=False)
    occupancy_rate = Column(Numeric(5, 2), default=0.00, nullable=False)
    calculated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    room = relationship("Room")
    
    __table_args__ = (
        UniqueConstraint("hotel_id", "room_id", "month", "year", name="uq_room_monthly_contribution"),
    )


# -------------------------------------------------------------
# 8. ENERGY & RESOURCE UTILITIES
# -------------------------------------------------------------

class UtilityMeter(Base):
    __tablename__ = "utility_meters"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    meter_type = Column(String(30), nullable=False) # ELECTRICITY, WATER, GAS
    room_id = Column(String(36), ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True) # null if master meter
    meter_number = Column(String(50), nullable=False)
    location_name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    room = relationship("Room")


class UtilityReading(Base):
    __tablename__ = "utility_readings"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    meter_id = Column(String(36), ForeignKey("utility_meters.id", ondelete="CASCADE"), nullable=False, index=True)
    reading_date = Column(Date, default=date.today, nullable=False)
    reading_value = Column(Numeric(10, 2), nullable=False)
    consumption_units = Column(Numeric(10, 2), default=0.00, nullable=False)
    cost_incurred = Column(Numeric(12, 2), default=0.00, nullable=False)
    bill_attachment_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    meter = relationship("UtilityMeter")


# -------------------------------------------------------------
# 9. REPORTING & NOTIFICATIONS
# -------------------------------------------------------------

class ReportSchedule(TimeStampedBase):
    __tablename__ = "report_schedules"
    
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    reporting_time = Column(String(10), default="23:59", nullable=False)
    timezone = Column(String(50), default="Asia/Kolkata", nullable=False)
    whatsapp_recipients = Column(JSON, default=list, nullable=False)
    email_recipients = Column(JSON, default=list, nullable=False)
    send_pdf_attachment = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class GeneratedReport(Base):
    __tablename__ = "generated_reports"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    report_date = Column(Date, nullable=False, index=True)
    report_type = Column(String(30), default="DAILY_EOD", nullable=False) # DAILY_EOD, MONTHLY_P_AND_L, INVENTORY_AUDIT
    report_data = Column(JSON, nullable=False)
    pdf_storage_path = Column(Text, nullable=True)
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        UniqueConstraint("hotel_id", "report_date", "report_type", name="uq_hotel_report_date_type"),
    )


class NotificationDeliveryLog(Base):
    __tablename__ = "notification_delivery_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    report_id = Column(String(36), ForeignKey("generated_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(20), nullable=False) # WHATSAPP, EMAIL, IN_APP
    recipient = Column(String(100), nullable=False)
    status = Column(String(20), default="PENDING", nullable=False) # PENDING, SENT, DELIVERED, FAILED
    error_message = Column(Text, nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    last_attempt_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


# -------------------------------------------------------------
# 10. AI ASSISTANT CONVERSATIONS & CONTROLLED LOGS
# -------------------------------------------------------------

class AssistantConversation(TimeStampedBase):
    __tablename__ = "assistant_conversations"
    
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(150), default="New Conversation", nullable=False)
    messages = relationship("AssistantMessage", back_populates="conversation", cascade="all, delete-orphan")


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender = Column(String(20), nullable=False) # USER, ASSISTANT, TOOL
    content = Column(Text, nullable=False)
    tool_calls = Column(JSON, default=list, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    conversation = relationship("AssistantConversation", back_populates="messages")


class AssistantToolLog(Base):
    __tablename__ = "assistant_tool_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    hotel_id = Column(String(36), ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    tool_name = Column(String(100), nullable=False)
    parameters_json = Column(JSON, default=dict, nullable=False)
    result_summary = Column(Text, nullable=True)
    execution_duration_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

