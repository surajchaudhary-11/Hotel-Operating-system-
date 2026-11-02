from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date, time
from decimal import Decimal

# -------------------------------------------------------------
# AUTH & PLATFORM SCHEMAS
# -------------------------------------------------------------

class UserRegister(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    phone_number: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    phone_number: Optional[str] = None
    is_active: bool
    is_platform_admin: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    memberships: List[Dict[str, Any]]

class HotelCreate(BaseModel):
    name: str
    address: str
    city: str = "Varanasi"
    state: str = "Uttar Pradesh"
    country: str = "India"
    postal_code: str
    phone: str
    email: EmailStr
    timezone: str = "Asia/Kolkata"
    currency: str = "INR"
    check_in_time: str = "12:00"
    check_out_time: str = "11:00"

class HotelUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    reporting_time: Optional[str] = None

class HotelResponse(BaseModel):
    id: str
    name: str
    slug: str
    address: str
    city: str
    state: str
    country: str
    postal_code: str
    phone: str
    email: str
    timezone: str
    currency: str
    check_in_time: str
    check_out_time: str
    reporting_time: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class HotelMembershipCreate(BaseModel):
    user_email: EmailStr
    role: str # OWNER, MANAGER, RECEPTIONIST, HOUSEKEEPING, MAINTENANCE, ACCOUNTANT

class HotelMembershipResponse(BaseModel):
    id: str
    user_id: str
    hotel_id: str
    role: str
    is_active: bool
    user: Optional[UserResponse] = None
    
    class Config:
        from_attributes = True

# -------------------------------------------------------------
# HOTEL STRUCTURE: FLOORS, ROOM TYPES, ROOMS
# -------------------------------------------------------------

class FloorCreate(BaseModel):
    floor_number: int
    name: str

class FloorResponse(BaseModel):
    id: str
    hotel_id: str
    floor_number: int
    name: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class RoomTypeCreate(BaseModel):
    name: str
    base_price: Decimal
    max_capacity: int = 2
    amenities: List[str] = []
    description: Optional[str] = None

class RoomTypeResponse(BaseModel):
    id: str
    hotel_id: str
    name: str
    base_price: Decimal
    max_capacity: int
    amenities: List[str]
    description: Optional[str] = None
    
    class Config:
        from_attributes = True

class RoomCreate(BaseModel):
    floor_id: str
    room_type_id: str
    room_number: str

class RoomStatusUpdate(BaseModel):
    status: str # VACANT_CLEAN, VACANT_DIRTY, OCCUPIED, INSPECTION_PENDING, INSPECTION_FAILED, BLOCKED_MAINTENANCE

class RoomResponse(BaseModel):
    id: str
    hotel_id: str
    floor_id: str
    room_type_id: str
    room_number: str
    status: str
    is_active: bool
    floor_name: Optional[str] = None
    room_type_name: Optional[str] = None
    base_price: Optional[Decimal] = None
    current_guest_name: Optional[str] = None
    
    class Config:
        from_attributes = True

# -------------------------------------------------------------
# INVENTORY & ASSETS
# -------------------------------------------------------------

class AssetCategoryCreate(BaseModel):
    name: str
    is_linen: bool = False
    is_consumable: bool = False
    low_stock_threshold: int = 5

class AssetCategoryResponse(BaseModel):
    id: str
    hotel_id: str
    name: str
    is_linen: bool
    is_consumable: bool
    low_stock_threshold: int
    total_assets_count: Optional[int] = 0
    
    class Config:
        from_attributes = True

class AssetCreate(BaseModel):
    category_id: str
    name: str
    asset_tag: Optional[str] = None
    current_location_type: str = "STORAGE" # ROOM, STORAGE, LAUNDRY, VENDOR, SCRAPPED
    current_room_id: Optional[str] = None
    condition: str = "GOOD"
    purchase_price: Decimal = Decimal("0.00")
    purchase_date: Optional[date] = None
    warranty_expiry: Optional[date] = None

class AssetResponse(BaseModel):
    id: str
    hotel_id: str
    category_id: str
    name: str
    asset_tag: Optional[str] = None
    qr_code_identifier: Optional[str] = None
    current_location_type: str
    current_room_id: Optional[str] = None
    current_room_number: Optional[str] = None
    category_name: Optional[str] = None
    condition: str
    purchase_price: Decimal
    purchase_date: Optional[date] = None
    warranty_expiry: Optional[date] = None
    is_active: bool
    
    class Config:
        from_attributes = True

class InventoryTransactionCreate(BaseModel):
    asset_id: Optional[str] = None
    category_id: str
    transaction_type: str # PURCHASE, ASSIGN_ROOM, RETURN_STORAGE, DISPATCH_LAUNDRY, RECEIVE_LAUNDRY, TRANSFER, MARK_DAMAGED, MARK_MISSING, DISCARD
    quantity: int
    from_location: str
    to_location: str
    unit_cost: Decimal = Decimal("0.00")
    reference_id: Optional[str] = None
    notes: Optional[str] = None

class InventoryTransactionResponse(BaseModel):
    id: str
    hotel_id: str
    asset_id: Optional[str] = None
    asset_name: Optional[str] = None
    category_id: str
    category_name: Optional[str] = None
    transaction_type: str
    quantity: int
    from_location: str
    to_location: str
    unit_cost: Decimal
    reference_id: Optional[str] = None
    notes: Optional[str] = None
    performed_by_name: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class InventoryAuditCreate(BaseModel):
    room_id: Optional[str] = None
    notes: Optional[str] = None

class InventoryAuditItemScan(BaseModel):
    asset_id: str
    expected_status: str
    actual_status: str
    discrepancy_type: Optional[str] = "NONE" # MISSING, DAMAGED, UNREGISTERED_FOUND, NONE
    notes: Optional[str] = None

# -------------------------------------------------------------
# OPERATIONS: HOUSEKEEPING, MAINTENANCE, LAUNDRY
# -------------------------------------------------------------

class HousekeepingTaskCreate(BaseModel):
    room_id: str
    assigned_to_user_id: Optional[str] = None
    priority: str = "NORMAL" # LOW, NORMAL, HIGH, URGENT
    notes: Optional[str] = None

class ChecklistUpdate(BaseModel):
    item_key: str
    is_completed: bool

class HousekeepingTaskResponse(BaseModel):
    id: str
    hotel_id: str
    room_id: str
    room_number: Optional[str] = None
    assigned_to_user_id: Optional[str] = None
    assigned_to_name: Optional[str] = None
    status: str
    priority: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    checklists: List[Dict[str, Any]] = []
    
    class Config:
        from_attributes = True

class InspectionSubmit(BaseModel):
    task_id: str
    room_id: str
    status: str # PASSED, FAILED
    rejection_reason: Optional[str] = None

class MaintenanceTicketCreate(BaseModel):
    room_id: Optional[str] = None
    asset_id: Optional[str] = None
    title: str
    description: str
    priority: str = "MEDIUM" # LOW, MEDIUM, HIGH, CRITICAL
    photo_urls: List[str] = []
    estimated_cost: Decimal = Decimal("0.00")

class MaintenanceUpdateCreate(BaseModel):
    message: str
    status_change: Optional[str] = None
    additional_cost: Decimal = Decimal("0.00")

class MaintenanceTicketResponse(BaseModel):
    id: str
    hotel_id: str
    room_id: Optional[str] = None
    room_number: Optional[str] = None
    asset_id: Optional[str] = None
    asset_name: Optional[str] = None
    title: str
    description: str
    priority: str
    status: str
    reported_by_name: Optional[str] = None
    assigned_technician_name: Optional[str] = None
    photo_urls: List[str] = []
    estimated_cost: Decimal
    actual_cost: Decimal
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updates: List[Dict[str, Any]] = []
    
    class Config:
        from_attributes = True

class LaundryVendorCreate(BaseModel):
    name: str
    contact_person: Optional[str] = None
    phone: str
    rate_per_kg: Optional[Decimal] = None
    rate_per_piece: Optional[Decimal] = None

class LaundryVendorResponse(BaseModel):
    id: str
    hotel_id: str
    name: str
    contact_person: Optional[str] = None
    phone: str
    rate_per_kg: Optional[Decimal] = None
    rate_per_piece: Optional[Decimal] = None
    is_active: bool
    
    class Config:
        from_attributes = True

class LaundryDispatchItem(BaseModel):
    category_id: str
    quantity_sent: int
    unit_cost: Decimal = Decimal("0.00")

class LaundryBatchDispatch(BaseModel):
    vendor_id: str
    expected_return_date: Optional[date] = None
    items: List[LaundryDispatchItem]

class LaundryReceiveItem(BaseModel):
    item_id: str
    quantity_received: int
    damaged_count: int = 0
    missing_count: int = 0

class LaundryBatchReceive(BaseModel):
    items: List[LaundryReceiveItem]

# -------------------------------------------------------------
# GUEST MANAGEMENT & DIGITAL CHECK-IN
# -------------------------------------------------------------

class GuestRegistrationRequest(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    phone: str
    id_type: Optional[str] = None
    id_number_masked: Optional[str] = None
    nationality: str = "Indian"
    city: Optional[str] = None
    state: Optional[str] = None

class GuestCheckInCreate(BaseModel):
    guest_id: Optional[str] = None # Existing guest ID, or supply new guest info
    guest_info: Optional[GuestRegistrationRequest] = None
    room_id: str
    expected_check_out_time: datetime
    adult_count: int = 1
    child_count: int = 0
    room_rate_per_night: Decimal
    advance_payment_amount: Decimal = Decimal("0.00")
    advance_payment_mode: Optional[str] = "UPI_QR"

class GuestCheckOutRequest(BaseModel):
    settlement_payment_amount: Decimal = Decimal("0.00")
    settlement_payment_mode: str = "CASH"
    notes: Optional[str] = None

class GuestStayResponse(BaseModel):
    id: str
    hotel_id: str
    guest_id: str
    guest_name: Optional[str] = None
    guest_phone: Optional[str] = None
    room_id: str
    room_number: Optional[str] = None
    check_in_time: datetime
    expected_check_out_time: datetime
    actual_check_out_time: Optional[datetime] = None
    status: str
    adult_count: int
    child_count: int
    room_rate_per_night: Decimal
    total_room_charge: Decimal
    total_tax_charge: Decimal
    total_additional_charge: Decimal
    total_paid: Decimal
    balance_due: Decimal
    registration_token: str
    booking_reference: Optional[str] = None
    booking_source: Optional[str] = "DIRECT"
    external_reference_id: Optional[str] = None
    group_booking_id: Optional[str] = None
    special_requests: Optional[str] = None
    estimated_arrival_time: Optional[str] = None
    payment_status: Optional[str] = "UNPAID"
    cancellation_reason: Optional[str] = None
    
    class Config:
        from_attributes = True

# -------------------------------------------------------------
# PHASE 2: RESERVATION & TAPE CHART SCHEMAS
# -------------------------------------------------------------

class ReservationCreate(BaseModel):
    guest_id: Optional[str] = None
    guest_info: Optional[GuestRegistrationRequest] = None
    room_id: str
    check_in_time: datetime
    expected_check_out_time: datetime
    adult_count: int = 1
    child_count: int = 0
    room_rate_per_night: Decimal
    booking_source: str = "DIRECT" # DIRECT, WALK_IN, PHONE, WEBSITE, BOOKING_COM, MAKEMYTRIP, GOIBIBO, AGODA, CORPORATE, TRAVEL_AGENT
    external_reference_id: Optional[str] = None
    special_requests: Optional[str] = None
    estimated_arrival_time: Optional[str] = "14:00"
    advance_payment_amount: Decimal = Decimal("0.00")
    advance_payment_mode: Optional[str] = "UPI_QR"

class GroupReservationItem(BaseModel):
    room_id: str
    room_rate_per_night: Decimal
    adult_count: int = 1
    child_count: int = 0
    guest_info: Optional[GuestRegistrationRequest] = None

class GroupReservationCreate(BaseModel):
    primary_guest_id: Optional[str] = None
    primary_guest_info: Optional[GuestRegistrationRequest] = None
    check_in_time: datetime
    expected_check_out_time: datetime
    booking_source: str = "DIRECT"
    external_reference_id: Optional[str] = None
    special_requests: Optional[str] = None
    estimated_arrival_time: Optional[str] = "14:00"
    rooms: List[GroupReservationItem]
    advance_payment_amount: Decimal = Decimal("0.00")
    advance_payment_mode: Optional[str] = "UPI_QR"

class ReservationUpdate(BaseModel):
    check_in_time: Optional[datetime] = None
    expected_check_out_time: Optional[datetime] = None
    room_rate_per_night: Optional[Decimal] = None
    adult_count: Optional[int] = None
    child_count: Optional[int] = None
    booking_source: Optional[str] = None
    external_reference_id: Optional[str] = None
    special_requests: Optional[str] = None
    estimated_arrival_time: Optional[str] = None

class ReservationCancelRequest(BaseModel):
    cancellation_reason: str
    refund_amount: Decimal = Decimal("0.00")
    refund_reason: Optional[str] = None

class RoomReassignRequest(BaseModel):
    new_room_id: str
    reason: Optional[str] = None

class ReservationPaymentCreate(BaseModel):
    amount: Decimal
    payment_mode: str = "UPI_QR" # CASH, UPI_QR, CREDIT_DEBIT_CARD, BANK_TRANSFER
    transaction_reference: Optional[str] = None
    notes: Optional[str] = None

class ReservationResponse(BaseModel):
    id: str
    hotel_id: str
    booking_reference: str
    booking_source: str
    external_reference_id: Optional[str] = None
    group_booking_id: Optional[str] = None
    guest_id: str
    guest_name: str
    guest_phone: str
    guest_email: Optional[str] = None
    room_id: str
    room_number: str
    room_type_name: Optional[str] = None
    floor_name: Optional[str] = None
    check_in_time: datetime
    expected_check_out_time: datetime
    actual_check_out_time: Optional[datetime] = None
    status: str
    adult_count: int
    child_count: int
    room_rate_per_night: Decimal
    total_room_charge: Decimal
    total_tax_charge: Decimal
    total_additional_charge: Decimal
    total_paid: Decimal
    balance_due: Decimal
    payment_status: str
    special_requests: Optional[str] = None
    estimated_arrival_time: Optional[str] = None
    cancellation_reason: Optional[str] = None
    registration_token: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class TapeChartBlock(BaseModel):
    reservation_id: str
    booking_reference: str
    guest_name: str
    guest_phone: str
    room_id: str
    room_number: str
    check_in_date: date
    check_out_date: date
    status: str
    booking_source: str
    payment_status: str
    total_paid: Decimal
    balance_due: Decimal

class TapeChartRoom(BaseModel):
    room_id: str
    room_number: str
    room_type: str
    floor_name: str
    current_status: str
    base_price: Decimal
    blocks: List[TapeChartBlock]

class TapeChartResponse(BaseModel):
    start_date: date
    end_date: date
    rooms: List[TapeChartRoom]

class RoomAvailabilityItem(BaseModel):
    room_id: str
    room_number: str
    floor_name: str
    room_type_id: str
    room_type_name: str
    base_price: Decimal
    max_occupancy: int
    is_available: bool

class RoomAvailabilityResponse(BaseModel):
    check_in_date: date
    check_out_date: date
    total_rooms: int
    available_rooms_count: int
    available_rooms: List[RoomAvailabilityItem]

# -------------------------------------------------------------
# FINANCIAL MANAGEMENT & ROOM PROFITABILITY
# -------------------------------------------------------------

class ExpenseCategoryCreate(BaseModel):
    name: str
    is_direct_room_expense: bool = False
    allocation_basis: str = "EQUAL_PER_ROOM" # DIRECT, EQUAL_PER_ROOM, OCCUPIED_ROOM_NIGHTS, ROOM_SQFT

class ExpenseCategoryResponse(BaseModel):
    id: str
    hotel_id: str
    name: str
    is_direct_room_expense: bool
    allocation_basis: str
    
    class Config:
        from_attributes = True

class ExpenseCreate(BaseModel):
    category_id: str
    room_id: Optional[str] = None
    amount: Decimal
    expense_date: date = Field(default_factory=date.today)
    payment_method: str = "UPI" # CASH, UPI, NEFT_RTGS, CARD, CREDIT_VENDOR
    invoice_url: Optional[str] = None
    description: str

class ExpenseResponse(BaseModel):
    id: str
    hotel_id: str
    category_id: str
    category_name: Optional[str] = None
    room_id: Optional[str] = None
    room_number: Optional[str] = None
    amount: Decimal
    expense_date: date
    payment_method: str
    invoice_url: Optional[str] = None
    description: str
    is_allocated: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class PaymentCreate(BaseModel):
    stay_id: str
    amount: Decimal
    payment_mode: str = "UPI_QR" # CASH, UPI_QR, CREDIT_DEBIT_CARD, BANK_TRANSFER
    transaction_reference: Optional[str] = None

class PaymentResponse(BaseModel):
    id: str
    hotel_id: str
    stay_id: str
    amount: Decimal
    payment_mode: str
    transaction_reference: Optional[str] = None
    payment_date: datetime
    collected_by_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class FinancialSummaryResponse(BaseModel):
    today_revenue: Decimal
    today_collections: Decimal
    today_expenses: Decimal
    today_operating_contribution: Decimal
    mtd_revenue: Decimal
    mtd_collections: Decimal
    mtd_expenses: Decimal
    mtd_operating_contribution: Decimal
    occupancy_rate: float
    total_rooms: int
    occupied_rooms: int
    vacant_rooms: int
    maintenance_rooms: int

class RoomProfitabilityItem(BaseModel):
    room_id: str
    room_number: str
    room_type: str
    available_nights: int
    occupied_nights: int
    occupancy_rate: float
    earned_revenue: Decimal
    direct_maintenance_expenses: Decimal
    allocated_expenses: Decimal
    operating_contribution: Decimal
    adr: Decimal
    revpar: Decimal

class ScenarioSimulationRequest(BaseModel):
    base_price: Decimal
    expected_occupancy_rate: float
    estimated_maintenance_monthly: Decimal
    estimated_allocated_utility_monthly: Decimal
    days_in_month: int = 30

class ScenarioSimulationResponse(BaseModel):
    simulated_monthly_revenue: Decimal
    simulated_operating_expenses: Decimal
    simulated_operating_contribution: Decimal
    simulated_adr: Decimal
    simulated_revpar: Decimal

# -------------------------------------------------------------
# UTILITY MANAGEMENT
# -------------------------------------------------------------

class UtilityMeterCreate(BaseModel):
    meter_type: str # ELECTRICITY, WATER, GAS
    room_id: Optional[str] = None
    meter_number: str
    location_name: str

class UtilityReadingCreate(BaseModel):
    meter_id: str
    reading_date: date = Field(default_factory=date.today)
    reading_value: Decimal
    consumption_units: Decimal
    cost_incurred: Decimal
    bill_attachment_url: Optional[str] = None

# -------------------------------------------------------------
# REPORTING & AI ASSISTANT
# -------------------------------------------------------------

class ReportScheduleUpdate(BaseModel):
    reporting_time: str = "23:59"
    timezone: str = "Asia/Kolkata"
    whatsapp_recipients: List[str] = []
    email_recipients: List[EmailStr] = []
    send_pdf_attachment: bool = True
    is_active: bool = True

class ActionProposal(BaseModel):
    action_id: str
    action_name: str
    title: str
    parameters: Dict[str, Any]
    impact_summary: str
    status: str = "pending_confirmation" # pending_confirmation, executed, cancelled

class AIChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    confirm_action_id: Optional[str] = None
    action_name: Optional[str] = None
    action_parameters: Optional[Dict[str, Any]] = None
    cancel_action_id: Optional[str] = None

class AIChatResponse(BaseModel):
    conversation_id: str
    message: str
    tools_executed: List[str] = []
    action_proposal: Optional[ActionProposal] = None
    action_executed: Optional[Dict[str, Any]] = None
    timestamp: datetime
