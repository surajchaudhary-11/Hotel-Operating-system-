# HotelOS — REST API Specification
**Version:** 1.0.0-PROD  
**Specification Standard:** OpenAPI 3.1 Aligned  
**Protocol:** HTTPS / JSON REST  
**Target Platform:** Multi-Tenant Hospitality Operating System

---

## 1. Global Architecture & Authentication

### 1.1 Base URLs
- **Local Development:** `http://localhost:8000/api/v1`
- **Render Production:** `https://api.hotelos.in/api/v1` (or `https://hotelos-backend.onrender.com/api/v1`)

### 1.2 Required Headers
| Header | Required For | Format | Description |
|---|---|---|---|
| `Authorization` | All authenticated routes | `Bearer <JWT_TOKEN>` | Cryptographically signed RS256/HS256 Supabase JWT |
| `X-Hotel-ID` | All tenant-scoped operations | `UUID` (e.g. `c7b3d820-...`) | Target hotel context. Backend verifies membership and active status. |
| `Content-Type` | All POST / PUT / PATCH endpoints | `application/json` | Request payload format |

### 1.3 Standard Error Responses
All 4xx and 5xx responses conform to the standard RFC 7807 / FastAPI envelope:
```json
{
  "detail": "Specific reason for rejection or validation failure"
}
```
Validation failures (`HTTP 422 Unprocessable Entity`) return:
```json
{
  "detail": [
    {
      "loc": ["body", "phone_number"],
      "msg": "Invalid Indian phone format. Must start with +91 or be 10 digits",
      "type": "value_error"
    }
  ]
}
```

---

## 2. Authentication & Identity (`/api/v1/auth`)

### `POST /auth/register`
Creates a new user account on the HotelOS platform.
- **Access:** Public
- **Request Body:**
  ```json
  {
    "email": "manager@varanasigrand.com",
    "password": "SecurePassword123!",
    "full_name": "Rajesh Kumar",
    "phone_number": "+919876543210"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "id": "u-a98f12-...",
    "email": "manager@varanasigrand.com",
    "full_name": "Rajesh Kumar",
    "phone_number": "+919876543210",
    "is_platform_admin": false,
    "created_at": "2026-10-31T08:00:00Z"
  }
  ```
- **Errors:** `400 Bad Request` (Email already registered).

---

### `POST /auth/login`
Authenticates a user and returns an access token.
- **Access:** Public
- **Request Body:**
  ```json
  {
    "email": "owner@kashiheritage.com",
    "password": "HotelOS2026!"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "user": {
      "id": "00000000-0000-0000-0000-000000000001",
      "email": "owner@kashiheritage.com",
      "full_name": "Aditya Sharma",
      "is_platform_admin": false
    }
  }
  ```
- **Errors:** `401 Unauthorized` (Invalid credentials or inactive account).

---

### `GET /auth/me`
Retrieves profile and active hotel memberships of the authenticated user.
- **Access:** Authenticated (`Authorization: Bearer <token>`)
- **Response (200 OK):**
  ```json
  {
    "id": "00000000-0000-0000-0000-000000000001",
    "email": "owner@kashiheritage.com",
    "full_name": "Aditya Sharma",
    "phone_number": "+919839012345",
    "is_platform_admin": false,
    "memberships": [
      {
        "hotel_id": "00000000-0000-0000-0000-000000000010",
        "hotel_name": "Kashi Heritage Haveli",
        "role": "OWNER",
        "is_active": true
      }
    ]
  }
  ```

---

## 3. Hotels & Multi-Tenancy (`/api/v1/hotels`)

### `GET /hotels`
Lists all hotels where the caller holds an active membership (or all hotels if platform admin).
- **Access:** Authenticated
- **Response (200 OK):** `list[HotelResponse]`
  ```json
  [
    {
      "id": "00000000-0000-0000-0000-000000000010",
      "name": "Kashi Heritage Haveli",
      "slug": "kashi-heritage-haveli",
      "city": "Varanasi",
      "state": "Uttar Pradesh",
      "currency": "INR",
      "timezone": "Asia/Kolkata",
      "is_active": true,
      "created_at": "2026-10-31T08:00:00Z"
    }
  ]
  ```

---

### `POST /hotels`
Onboards a new hotel property and grants the caller `OWNER` membership.
- **Access:** Authenticated
- **Request Body:**
  ```json
  {
    "name": "Ganga View Boutique Hotel",
    "address": "Assi Ghat Road",
    "city": "Varanasi",
    "state": "Uttar Pradesh",
    "country": "India",
    "postal_code": "221005",
    "phone": "+915422314567",
    "email": "reservations@gangaview.com",
    "timezone": "Asia/Kolkata",
    "currency": "INR",
    "check_in_time": "14:00:00",
    "check_out_time": "11:00:00"
  }
  ```
- **Response (200 OK):** `HotelResponse` with auto-generated unique slug `ganga-view-boutique-hotel`.

---

### `GET /hotels/{hotel_id}/members`
Retrieves the staff list and assigned roles for a property.
- **Access:** `OWNER`, `MANAGER`
- **Headers:** `X-Hotel-ID: <hotel_id>`
- **Response (200 OK):**
  ```json
  [
    {
      "membership_id": "mem-101",
      "user_id": "usr-501",
      "full_name": "Ramesh Maurya",
      "email": "ramesh@kashiheritage.com",
      "phone_number": "+919450123456",
      "role": "RECEPTIONIST",
      "joined_at": "2026-10-31T08:00:00Z"
    }
  ]
  ```

---

### `POST /hotels/{hotel_id}/members`
Adds a user to the property team by registered email.
- **Access:** `OWNER`
- **Request Body:**
  ```json
  {
    "user_email": "accountant@kashiheritage.com",
    "role": "ACCOUNTANT"
  }
  ```
- **Errors:** `404 Not Found` (Target user does not have a HotelOS account).

---

## 4. Rooms & Floors (`/api/v1/rooms`)

### `GET /rooms`
Fetches all configured rooms with current status, floor name, room type base rate, and checked-in guest name.
- **Access:** Tenant Member
- **Headers:** `X-Hotel-ID: <hotel_id>`
- **Response (200 OK):**
  ```json
  [
    {
      "id": "rm-101-uuid",
      "hotel_id": "00000000-0000-0000-0000-000000000010",
      "floor_id": "fl-01-uuid",
      "room_type_id": "rt-dlx-uuid",
      "room_number": "101",
      "status": "OCCUPIED",
      "is_active": true,
      "floor_name": "First Floor",
      "room_type_name": "Heritage Deluxe",
      "base_price": 3500.00,
      "current_guest_name": "Vikram Malhotra"
    }
  ]
  ```

---

### `POST /rooms`
Creates a new physical room under an existing floor and room type.
- **Access:** `OWNER`, `MANAGER`
- **Headers:** `X-Hotel-ID: <hotel_id>`
- **Request Body:**
  ```json
  {
    "floor_id": "fl-01-uuid",
    "room_type_id": "rt-dlx-uuid",
    "room_number": "105"
  }
  ```
- **Errors:** `400 Bad Request` (Room number already exists in hotel).

---

### `PATCH /rooms/{room_id}/status`
Overrides or updates room housekeeping / maintenance status.
- **Access:** `OWNER`, `MANAGER`, `RECEPTIONIST`, `HOUSEKEEPING`
- **Request Body:**
  ```json
  {
    "status": "VACANT_CLEAN"
  }
  ```
- **Valid Statuses:** `VACANT_CLEAN`, `VACANT_DIRTY`, `OCCUPIED`, `INSPECTION_PENDING`, `INSPECTION_FAILED`, `BLOCKED_MAINTENANCE`.

---

### `GET /rooms/{room_id}/details`
Room 360 View: Fetches comprehensive room specifications, current stay, assigned fixed assets, recent maintenance tickets, and cleaning logs.
- **Access:** Tenant Member
- **Response (200 OK):**
  ```json
  {
    "room": {
      "id": "rm-101",
      "room_number": "101",
      "status": "OCCUPIED",
      "floor_name": "Ground Floor",
      "room_type_name": "Heritage Suite",
      "base_price": 5500.0,
      "amenities": ["Ganga View Balcony", "Air Conditioner", "Mini Fridge"]
    },
    "current_stay": {
      "stay_id": "sty-201",
      "guest_name": "Vikram Malhotra",
      "phone": "+919811223344",
      "check_in_time": "2026-10-31T14:00:00Z",
      "expected_check_out_time": "2026-11-03T11:00:00Z",
      "balance_due": 3920.0
    },
    "assets": [
      {
        "id": "ast-301",
        "name": "Daikin Inverter AC 1.5 Ton",
        "asset_tag": "AST-AC-101",
        "condition": "GOOD",
        "qr_code_identifier": "QR-HOTELOS-000000-DAI-123456"
      }
    ],
    "recent_tickets": [],
    "recent_cleaning": []
  }
  ```

---

### `GET /rooms/floors` & `POST /rooms/floors`
Lists or creates property floors (e.g. Ground Floor, First Floor).

### `GET /rooms/room-types` & `POST /rooms/room-types`
Lists or creates room categories with base pricing, capacity, and amenities.

---

## 5. Inventory, Assets & QR Ledger (`/api/v1/inventory`)

### `GET /inventory/categories`
Lists inventory and asset categories with count of active tagged assets.
- **Access:** Tenant Member
- **Response (200 OK):**
  ```json
  [
    {
      "id": "cat-lin-01",
      "hotel_id": "00000000-0000-0000-0000-000000000010",
      "name": "Bedsheet King Cotton",
      "is_linen": true,
      "is_consumable": false,
      "low_stock_threshold": 10,
      "total_assets_count": 45
    }
  ]
  ```

---

### `GET /inventory/assets`
Lists individual tracked assets (ACs, Smart TVs, Geysers, Linens) with current location and room binding.
- **Access:** Tenant Member
- **Response (200 OK):** `list[AssetResponse]`

---

### `POST /inventory/assets`
Registers a new asset into the hotel registry. Automatically generates a unique QR identifier and posts an initial `PURCHASE` transaction into the immutable inventory ledger.
- **Access:** `OWNER`, `MANAGER`
- **Request Body:**
  ```json
  {
    "category_id": "cat-elec-01",
    "name": "Samsung 43\" Smart TV",
    "asset_tag": "AST-TV-204",
    "current_location_type": "ROOM",
    "current_room_id": "rm-204-uuid",
    "condition": "NEW",
    "purchase_price": 28500.00,
    "purchase_date": "2026-10-15",
    "warranty_expiry": "2028-10-14"
  }
  ```

---

### `GET /inventory/transactions`
Fetches the immutable ledger of all stock movements, laundry dispatches, room assignments, and write-offs.
- **Access:** Tenant Member
- **Response (200 OK):**
  ```json
  [
    {
      "id": "tx-801",
      "asset_name": "Samsung 43\" Smart TV",
      "category_name": "Electronics",
      "transaction_type": "PURCHASE",
      "quantity": 1,
      "from_location": "VENDOR",
      "to_location": "ROOM",
      "unit_cost": 28500.00,
      "notes": "Initial registration of asset into system",
      "performed_by_name": "Aditya Sharma",
      "created_at": "2026-10-31T08:30:00Z"
    }
  ]
  ```

---

### `POST /inventory/transactions`
Appends a movement to the ledger. Validates physical quantity constraints.
- **Access:** Tenant Member
- **Request Body:**
  ```json
  {
    "category_id": "cat-lin-01",
    "asset_id": null,
    "transaction_type": "ISSUE_TO_ROOM",
    "quantity": 4,
    "from_location": "STORAGE",
    "to_location": "ROOM",
    "reference_id": "rm-102-uuid",
    "notes": "Replenishment for Room 102"
  }
  ```

---

### `GET /inventory/qr/generate?code=<qr_string>`
Generates and returns an on-the-fly high-resolution PNG QR Code image for physical asset tags and room door placards.
- **Access:** Tenant Member
- **Response:** `image/png` binary stream.

---

## 6. Hotel Operations (`/api/v1/operations`)

### Housekeeping

#### `GET /operations/housekeeping/tasks`
Lists cleaning tasks with room numbers, priorities, checklists, and assigned attendants.
- **Access:** Tenant Member

#### `POST /operations/housekeeping/tasks`
Creates a cleaning task for a room and injects the 5-point hospitality checklist.
- **Access:** `OWNER`, `MANAGER`, `RECEPTIONIST`
- **Request Body:**
  ```json
  {
    "room_id": "rm-101-uuid",
    "priority": "HIGH",
    "notes": "VIP guest arriving at 2:00 PM"
  }
  ```

#### `PATCH /operations/housekeeping/tasks/{task_id}/start`
Sets task to `IN_PROGRESS` and stamps `started_at`.
- **Access:** Assigned Staff, `MANAGER`, `OWNER`

#### `PATCH /operations/housekeeping/tasks/{task_id}/checklist`
Marks a specific checklist item complete/incomplete.
- **Request Body:**
  ```json
  {
    "item_key": "Change bedsheets and pillow covers",
    "is_completed": true
  }
  ```

#### `PATCH /operations/housekeeping/tasks/{task_id}/complete`
Marks task as completed, transitioning room to `INSPECTION_PENDING`.

#### `POST /operations/housekeeping/inspections`
Supervisor submits formal room inspection.
- **Access:** `OWNER`, `MANAGER`
- **Request Body:**
  ```json
  {
    "task_id": "tsk-101",
    "room_id": "rm-101",
    "status": "PASSED",
    "rejection_reason": null
  }
  ```
- **Effect:** If `PASSED`, transitions room to `VACANT_CLEAN`. If `FAILED`, transitions room to `INSPECTION_FAILED`.

---

### Maintenance

#### `GET /operations/maintenance/tickets`
Lists maintenance tickets with room/asset bindings, photo attachments, and updates.

#### `POST /operations/maintenance/tickets`
Logs a ticket. If priority is `CRITICAL`, automatically updates room status to `BLOCKED_MAINTENANCE`.
- **Request Body:**
  ```json
  {
    "room_id": "rm-102-uuid",
    "asset_id": "ast-ac-02",
    "title": "Air Conditioner blowing warm air",
    "description": "Compressor failing to start. Error code E4 on panel.",
    "priority": "CRITICAL",
    "estimated_cost": 2500.00,
    "photo_urls": ["https://storage.supabase.co/hotelos/tickets/ac-error.jpg"]
  }
  ```

#### `POST /operations/maintenance/tickets/{ticket_id}/updates`
Logs repairs, technician notes, additional expenses, or resolves the ticket.
- **Effect:** If status changes to `RESOLVED`, automatically unblocks the room, moving it to `VACANT_DIRTY` for cleaning.

---

### Linen & Laundry

#### `GET /operations/laundry/vendors` & `POST /operations/laundry/vendors`
Configures third-party dhobi / industrial laundry partners with contractual rates per kg or piece.

#### `POST /operations/laundry/batches/dispatch`
Creates a dispatch consignment, automatically recording outbound movement (`STORAGE` -> `LAUNDRY_VENDOR`) in the inventory ledger.
- **Request Body:**
  ```json
  {
    "vendor_id": "vnd-01",
    "expected_return_date": "2026-11-02",
    "items": [
      {
        "category_id": "cat-lin-01",
        "quantity_sent": 25,
        "unit_cost": 15.00
      }
    ]
  }
  ```

---

## 7. Guests, Stays & Front Desk (`/api/v1/guests`)

### `GET /guests/stays`
Lists guest stays across `CHECKED_IN`, `CHECKED_OUT`, and `CANCELLED`.
- **Access:** Tenant Member
- **Headers:** `X-Hotel-ID: <hotel_id>`

---

### `POST /guests/check-in`
Executes front desk walk-in check-in:
1. Creates or matches guest record (auto-masking Aadhaar/Passport numbers).
2. Validates room readiness (`VACANT_CLEAN` or `VACANT_DIRTY`).
3. Sets room status to `OCCUPIED`.
4. Posts Day-1 room tariff to earned `Revenue`.
5. Records advance payment (if collected) in `Payment`.
6. Generates a secure, 32-character digital check-in registration token.
- **Request Body:**
  ```json
  {
    "guest_info": {
      "full_name": "Siddharth Verma",
      "phone": "+919876543210",
      "email": "siddharth@gmail.com",
      "id_type": "AADHAAR",
      "id_number_masked": "567812349012",
      "city": "Lucknow",
      "state": "Uttar Pradesh",
      "nationality": "Indian"
    },
    "room_id": "rm-103-uuid",
    "expected_check_out_time": "2026-11-02T11:00:00Z",
    "adult_count": 2,
    "child_count": 0,
    "room_rate_per_night": 3200.00,
    "advance_payment_amount": 3584.00,
    "advance_payment_mode": "UPI_QR"
  }
  ```

---

### `POST /guests/stays/{stay_id}/checkout`
Finalizes stay folio, accepts final settlement payment, updates stay status to `CHECKED_OUT`, and marks room as `VACANT_DIRTY`.
- **Request Body:**
  ```json
  {
    "settlement_payment_amount": 1200.00,
    "settlement_payment_mode": "CASH"
  }
  ```

---

### `GET /guests/digital-checkin/{token}`
Public endpoint for mobile guest self check-in landing page. Returns reservation overview and check-in greeting without leaking other guests' data.
- **Access:** Public (Protected by cryptographic random token)

### `POST /guests/digital-checkin/{token}/submit`
Allows guest to verify their details, upload required travel info, and accept house rules prior to key collection.
- **Access:** Public

---

## 8. Finance, Operating Contribution & Simulation (`/api/v1/finance`)

### `GET /finance/summary`
Returns comprehensive USALI-aligned financial metrics:
- Today's Earned Revenue vs. Cash Collections.
- Today's Operating Expenses.
- Today's Operating Contribution (`Earned Revenue - Operating Expenses`).
- Month-To-Date (MTD) aggregations.
- Real-time room occupancy count and percentage.
- **Access:** `OWNER`, `MANAGER`, `ACCOUNTANT`
- **Response (200 OK):**
  ```json
  {
    "today_revenue": 14200.00,
    "today_collections": 17800.00,
    "today_expenses": 3450.00,
    "today_operating_contribution": 10750.00,
    "mtd_revenue": 384000.00,
    "mtd_collections": 412000.00,
    "mtd_expenses": 112500.00,
    "mtd_operating_contribution": 271500.00,
    "occupancy_rate": 78.5,
    "total_rooms": 20,
    "occupied_rooms": 16,
    "vacant_rooms": 3,
    "maintenance_rooms": 1
  }
  ```

---

### `GET /finance/expenses` & `POST /finance/expenses`
Lists and logs operational expenses (Housekeeping supplies, Utilities, Maintenance, Laundry, Staff wages). Supports direct room allocation (`room_id`) or property-wide allocation (`is_allocated=true`).

---

### `GET /finance/room-profitability`
Calculates month-to-date financial performance for each individual room:
- Total room nights occupied.
- Revenue earned.
- Direct maintenance costs incurred.
- Allocated shared property expenses.
- Operating Contribution.
- **Access:** `OWNER`, `MANAGER`, `ACCOUNTANT`

---

### `POST /finance/scenario-simulation`
Real-time financial simulation engine for hotel owners to model occupancy and tariff changes:
- **Request Body:**
  ```json
  {
    "total_rooms": 20,
    "current_adr": 3500.00,
    "current_occupancy_percent": 65.0,
    "fixed_monthly_expenses": 120000.00,
    "variable_cost_per_occupied_room": 350.00,
    "target_occupancy_percent": 80.0,
    "target_adr": 3800.00
  }
  ```
- **Response (200 OK):** Current vs. Projected Revenue, Total Operating Costs, Operating Contribution, and Break-Even Occupancy percentage.

---

## 9. Utilities & Energy Tracking (`/api/v1/utilities`)

### `GET /utilities/meters` & `POST /utilities/meters`
Manages electric and water sub-meters (master hotel meters, floor-wise meters, or room-wise meters).

### `GET /utilities/readings` & `POST /utilities/readings`
Records utility meter readings with date, cumulative units, consumption delta, bill cost, and invoice attachment URL.

---

## 10. Reporting & Night Audit (`/api/v1/reports`)

### `POST /reports/trigger-audit`
Manually triggers or tests the automated end-of-day Night Audit pipeline.
- **Parameters:** `audit_date` (optional, defaults to current date).
- **Access:** `OWNER`, `MANAGER`
- **Response (200 OK):**
  ```json
  {
    "message": "Night Audit executed successfully",
    "report": {
      "audit_date": "2026-10-31",
      "total_rooms": 20,
      "occupied_rooms": 16,
      "occupancy_percent": 80.0,
      "adr": 3550.00,
      "revpar": 2840.00,
      "room_revenue": 56800.00,
      "cash_collections": 61200.00,
      "total_expenses": 9400.00,
      "operating_contribution": 47400.00,
      "unresolved_maintenance_tickets": 2,
      "dirty_rooms_pending": 1
    }
  }
  ```

---

### `GET /reports/daily`
Retrieves the finalized Night Audit summary JSON for any calendar date. If the audit has not executed yet, runs an in-memory live projection.
- **Access:** `OWNER`, `MANAGER`, `ACCOUNTANT`

---

### `GET /reports/daily/pdf`
Generates and downloads the executive Daily Night Audit PDF report, complete with key operational and financial indicators, room status summary, and expense breakdown.
- **Response:** `application/pdf` binary stream (`Content-Disposition: attachment; filename="HotelOS_Daily_Report_...pdf"`).

---

### `GET /reports/settings` & `PUT /reports/settings`
Configures automated nightly dispatch preferences (execution time `23:59`, Asia/Kolkata timezone, WhatsApp phone numbers, recipient email addresses, PDF attachment toggle).

---

## 11. AI Hotel Operations Assistant (`/api/v1/ai`)

### `POST /ai/chat`
Processes conversational inquiries from hotel owners and managers using permission-aware, read-only analytical tool bindings.
- **Access:** Authenticated Tenant Member
- **Request Body:**
  ```json
  {
    "message": "How many rooms are occupied today, and what are today's total expenses?",
    "conversation_id": "conv-101"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "conversation_id": "conv-101",
    "response": "As of today, 16 out of 20 rooms (80.0%) are occupied. Today's recorded operating expenses total ₹9,400.00, yielding an operating contribution of ₹47,400.00.",
    "tool_calls": [
      {
        "tool": "get_occupancy_metrics",
        "result": {"occupied": 16, "total": 20, "rate": 80.0}
      },
      {
        "tool": "get_financial_metrics",
        "result": {"revenue": 56800.0, "expenses": 9400.0}
      }
    ]
  }
  ```

---

### `GET /ai/conversations` & `GET /ai/conversations/{id}/messages`
Retrieves chat history and message logs for the active user.

---

## 12. Planned Endpoints (Architecture Roadmap)

The following endpoints are specified for upcoming development phases:
1. `GET /api/v1/bookings/calendar` — Matrix of room availabilities and reservations across a 30-day window.
2. `POST /api/v1/bookings` — Reservation creation with date-range double-booking conflict rejection.
3. `POST /api/v1/inventory/audits` — Periodic physical inventory discrepancy reconciliation.
4. `POST /api/v1/procurement/orders` — General vendor purchase orders for guest amenities and groceries.
5. `POST /api/v1/employees/attendance/punch` — Biometric / Geofenced staff shift tracking.

