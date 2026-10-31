# HotelOS — Product Requirements Document (PRD)
**System Class:** Multi-Tenant B2B Hospitality Operating System  
**Target Market:** Independent, Heritage & Mid-Sized Hotels in India (Initial Launch: Varanasi, UP)  
**Document Version:** 2.0.0 — Production Blueprint  
**Status:** Approved Technical Specification  

---

## 1. Executive Product Vision & Domain Context

Independent and mid-sized hotels in India—particularly in high-density heritage markets like Varanasi—suffer from severe operational fragmentation. Front desk operations rely on paper registers or disconnected spreadsheets; housekeeping coordination occurs via ad-hoc WhatsApp groups; linen shrinkage and missing room assets remain untracked; and utility expenses (especially commercial power tariffs from UPPCL) are rarely reconciled with room-level occupancy. Most critically, owners confuse gross cash collections with earned accrual revenue, creating distorted tax assumptions and financial blind spots.

**HotelOS** replaces this disjointed stack with an integrated, multi-tenant property operations, inventory, financial, and reporting operating system. The platform treats every guest stay, asset movement, housekeeping cleaning, and expense entry as an auditable ledger record.

---

## 2. Executive Owner Dashboard

The Executive Dashboard serves as the central command center for hotel owners, general managers, and operational supervisors. Every data point is dynamically computed from underlying transactional records for the active hotel context.

### 2.1 Room Status & Occupancy KPI Pipeline
- **Total Rooms**: Physical count of active, sellable room keys registered to the property.
- **Occupied Rooms**: Count of rooms with an active `CHECKED_IN` stay record on the current business date.
- **Vacant Clean (Ready)**: Rooms that have passed supervisor inspection and are sellable for immediate guest check-in.
- **Vacant Dirty (Housekeeping)**: Rooms vacated upon checkout or requiring daily occupied freshening.
- **Inspection Pending**: Rooms marked cleaned by housekeeping awaiting supervisor sign-off.
- **Inspection Failed**: Rooms rejected by supervisor during inspection, queued for priority re-cleaning.
- **Blocked for Maintenance**: Rooms with active `CRITICAL` maintenance tickets removed from sellable inventory.
- **Occupancy Percentage**:
  $$\text{Occupancy Rate (\%)} = \left(\frac{\text{Occupied Room Nights}}{\text{Available Room Nights}}\right) \times 100$$
  *Where Available Room Nights = Total Keys − Blocked Maintenance Keys.*

### 2.2 Financial Overview (Accrual vs. Cash Flow Distinction)
- **Earned Revenue (Accrual)**: Room tariff and incidental service charges legally earned during the business date, posted automatically during the nightly Night Audit.
- **Cash Collections (Inflow)**: Total actual money collected today across cash, UPI QR, debit/credit cards, and bank transfers (settling advances, current folios, or past receivables).
- **Accounts Receivable (Folio Balances)**: Cumulative unsettled balances across all currently in-house or departing guests.
- **Recorded Operating Expenses**: Sum of all validated operational expense vouchers logged on the current date (distinguishing direct room expenses from shared facility costs).
- **Operating Contribution (GOP Level)**:
  $$\text{Operating Contribution} = \text{Earned Revenue} - \text{Direct Expenses} - \text{Allocated Shared Expenses}$$
  *Strictly labeled as Operating Contribution under USALI standards—never labeled as Net Profit.*

### 2.3 Operational Action Queues
- **Urgent Maintenance**: Live counter of open tickets with priority `HIGH` or `CRITICAL`.
- **Asset Discrepancies**: Live counter of assets flagged as `DAMAGED` or `MISSING` requiring management reconciliation.
- **Linen In-Transit**: Volume of bedsheets and towels currently in custody of commercial laundry vendors.
- **Housekeeping Backlog**: Rooms remaining in `VACANT_DIRTY` state exceeding 120 minutes from checkout.

### 2.4 Analytics & Visual Trends
- **7-Day Financial Performance Chart**: Multi-bar/line chart comparing Earned Accrual Revenue, Cash Collections, and Expenses.
- **Room Performance Ranking**: Top 5 earning rooms vs. highest operating cost rooms.
- **Monthly Budget vs. Actual**: Percentage variance of utility and consumable spending against configured monthly budgets.

---

## 3. Booking & Reservation Management

Booking management is a core foundational module ensuring zero double-bookings through atomic database-level constraints.

### 3.1 Functional Requirements
1. **Reservation Sources**:
   - Categorize bookings by source: `DIRECT_WALK_IN`, `PHONE_DIRECT`, `WEBSITE_DIRECT`, `OTA_BOOKING_COM`, `OTA_MAKEMYTRIP`, `OTA_AGODA`, `CORPORATE`.
2. **Room Allocation & Inventory Lock**:
   - Booking creation requires date range (`check_in_date`, `check_out_date`), room category (`room_type_id`), and explicit room assignment (`room_id`).
   - Atomic reservation transaction checks date-range overlap against existing `RESERVED` and `CHECKED_IN` stays using PostgreSQL range exclusion constraints (`tstzrange`).
3. **Rate Plans & Pricing**:
   - Support `STANDARD_EP` (Room Only), `CP` (Continental Plan / Bed & Breakfast), `MAP` (Modified American Plan / Breakfast + Dinner), and `AP` (American Plan / All Meals).
   - Dynamic seasonal tariff overrides.
4. **Deposit & Advance Payments**:
   - Log advance booking deposits directly against the booking entity with payment mode and gateway/UPI reference.
   - Support partial deposits, refundable holding fees, and non-refundable peak season guarantees.
5. **Modification & Cancellation Workflow**:
   - Date modifications verify inventory availability before updating check-in/out timestamps.
   - Cancellations record reason, calculate cancellation charges according to property policy, and issue refund vouchers.
6. **No-Show Handling**:
   - Automated flagging of unarrived reservations past 23:59 on scheduled arrival date during the Night Audit.

---

## 4. Room & Property Management

### 4.1 Structural Hierarchy
- **Property**: Master hotel entity storing tax registration (GSTIN), contact details, standard check-in (12:00 PM) and check-out (11:00 AM) policies, and operating timezone (`Asia/Kolkata`).
- **Floors**: Floor numbers and heritage wing names (e.g., *Ground Courtyard*, *Ganga View Floor*, *Rooftop Terrace*).
- **Room Types**: Categories defining maximum adult/child capacity, base tariff, bed configuration, and amenities.
- **Individual Rooms**: Physical rooms assigned to a floor and type with a unique room number.

### 4.2 Room State Machine
```
[VACANT_CLEAN] ──(Check-In)──> [OCCUPIED]
       ▲                             │
       │                         (Check-Out)
(Inspection Passed)                  │
       │                             ▼
[INSPECTION_PENDING] <──(Cleaned)── [VACANT_DIRTY]
       │                             ▲
(Inspection Failed)                  │
       │                             │
       ▼                             │
[INSPECTION_FAILED] ──(Re-clean)─────┘
       │
(Critical Breakdown) ──> [BLOCKED_MAINTENANCE] ──(Resolved)──> [VACANT_DIRTY]
```

### 4.3 Room 360° Profile
Every room detail view aggregates:
1. Physical asset inventory currently housed in the room.
2. Complete stay and occupancy history (past guests, folio totals).
3. Housekeeping cleaning logs with start/end timestamps and cleaner identity.
4. Maintenance ticket history and cumulative repair costs.
5. Lifetime and MTD revenue, direct repair costs, allocated shared costs, and operating contribution.

---

## 5. Asset & Inventory Management (Double-Entry Ledger)

HotelOS prohibits static stock quantity overwrites. Every physical item movement is recorded as an immutable, double-entry transaction record.

### 5.1 Asset Catalog & Tracking
- **Linen Assets**: Bedsheets, duvet covers, pillowcases, bath towels, hand towels, pool towels, bath mats.
- **Electronics & Appliances**: Smart TVs, remotes, split ACs, ceiling fans, mini-fridges, electric kettles, geysers.
- **Furniture & Fixtures**: King beds, mattresses, bedside tables, wardrobes, vanity mirrors, sanitary fittings.
- **Consumables**: Toiletries, water bottles, tea/coffee sachets, cleaning chemicals.

### 5.2 Physical Locations
- `CENTRAL_STORAGE`: Main warehouse/pantry buffer stock.
- `ROOM_{NUMBER}`: Placed inside guest room.
- `FLOOR_PANTRY`: Housekeeping floor distribution carts.
- `LAUNDRY_VENDOR`: External commercial laundry facility.
- `MAINTENANCE_CUSTODY`: Under repair in technician workshop.
- `SCRAPPED`: Discarded, written off, or permanently retired.

### 5.3 Transaction Types & Rules
- `PURCHASE`: Vendor → Central Storage (increases total inventory valuation).
- `ASSIGN_ROOM`: Central Storage / Floor Pantry → Room (links asset to `room_id`).
- `RETURN_STORAGE`: Room → Central Storage (unlinks from `room_id`).
- `DISPATCH_LAUNDRY`: Floor Pantry / Storage → Laundry Vendor.
- `RECEIVE_LAUNDRY`: Laundry Vendor → Storage (reconciles returned counts).
- `MARK_DAMAGED`: Condition updated to `DAMAGED` (creates maintenance ticket or scrap voucher).
- `MARK_MISSING`: Condition updated to `MISSING` (creates audit discrepancy alert).
- `DISCARD`: Retired from active circulation with write-off reason.

### 5.4 QR Tagging & Room Auditing
- System generates unique alphanumeric identifiers and printable QR codes for every asset and room tag.
- Staff scan room door QR code to open room inventory checklist, then scan individual asset QR tags to verify physical presence and condition.
- Immediate discrepancy logging if an asset expected in Room 101 is missing or scanned in Room 204.

---

## 6. Housekeeping Management

### 6.1 Workflow & Roles
1. Room transitions to `VACANT_DIRTY` automatically upon front-desk check-out or daily morning schedule.
2. Manager/Supervisor assigns cleaning task to a specific housekeeper.
3. Housekeeper logs in on mobile PWA, views assigned rooms, and taps **Start Cleaning** (records exact start timestamp).
4. Housekeeper completes room-specific checklist items:
   - Strip soiled bedsheets and pillow covers.
   - Sanitize bathroom tiles, fittings, and commode.
   - Dust wood furniture and vacuum rugs.
   - Restock complimentary drinking water and tea station.
   - Test TV remote and AC cooling.
5. If an item is found damaged or missing during cleaning, staff taps **Report Discrepancy** with mandatory photo upload, automatically generating a Maintenance Ticket and Inventory Alert.
6. Housekeeper taps **Complete Cleaning** (records completion timestamp, moves room state to `INSPECTION_PENDING`).
7. Supervisor physically audits the room and submits inspection:
   - **Passed**: Room immediately updates to `VACANT_CLEAN` and appears ready for front-desk allocation.
   - **Failed**: Room transitions to `INSPECTION_FAILED` with mandatory rejection notes, re-dispatching a priority cleaning task.

---

## 7. Maintenance & Appliance Management

### 7.1 Breakdown Ticketing
- **Ticket Creation**: Front desk, housekeeping, or management creates tickets specifying `room_id`, `asset_id`, issue category (Electrical, Plumbing, HVAC, Carpentry), priority, and photo attachments.
- **Priority Rules**:
  - `CRITICAL`: Issues causing room inhabitable status (e.g., AC failure during Varanasi summer, water pipe burst). Automatically forces room into `BLOCKED_MAINTENANCE`.
  - `HIGH`: Major inconvenience (e.g., TV display flicker, geyser thermostat error).
  - `MEDIUM` / `LOW`: Minor cosmetic issues (e.g., loose wardrobe hinge).
- **Technician Updates**: Technicians log status transitions (`IN_PROGRESS`, `WAITING_PARTS`, `RESOLVED`), work descriptions, parts replaced, and additional expenditure incurred.
- **Resolution & Unblocking**: Marking a critical ticket `RESOLVED` automatically transitions the room to `VACANT_DIRTY` (requiring housekeeping cleaning before guest check-in).

---

## 8. Linen & Commercial Laundry Management

Linen loss and quality degradation represent major hidden operating expenses for Varanasi hotels. HotelOS enforces a strict 3-way custody cycle.

### 8.1 3-Way Custody Cycle
1. **Soiled Linen Collection**: Collected from guest rooms and counted into `STORAGE_DIRTY`.
2. **Batch Dispatch**: Manager creates a dispatch batch selecting the contracted commercial laundry vendor, logging exact item counts (e.g., 50 Bedsheets, 40 Towels). Inventory ledger logs transfer from `STORAGE` to `LAUNDRY_VENDOR`.
3. **Batch Receipt & Reconciliation**: Upon vendor delivery, supervisor opens the batch receipt screen and enters delivered counts:
   - *Clean Intact Items*: Transferred to `STORAGE_CLEAN`.
   - *Torn / Burned Items*: Logged as `DAMAGED` (deducted from vendor payment voucher).
   - *Shortages*: Logged as `MISSING` (penalized against vendor contract).
4. **Expense Tracking**: Calculates exact cost per wash cycle and cost per occupied room-night.

---

## 9. Employee Management & Role-Based Access Control

### 9.1 Staff Profiles & Shifts
- Manage employee code, full name, phone number, department, shift (Morning, Evening, Night, Rotational), date of joining, and salary.
- Daily attendance tracking (Present, Absent, Half-Day, Approved Leave) with check-in/out timestamps.

### 9.2 Audit Logging
- System captures immutable audit logs for sensitive operations:
  - Room status manual overrides.
  - Cash payment collections and refunds.
  - Expense approvals and manual ledger adjustments.
  - Guest document access and downloads.
  - Captures `user_id`, `action_type`, `entity_type`, `entity_id`, IP address, and before/after JSON payloads.

---

## 10. Guest Management & Digital Self Check-In

### 10.1 Front Desk Folio Workflow
- Guest register captures primary guest details, accompanied guests (adults/children), origin city, and contact info.
- Front desk check-in assigns an inspected clean room, posts initial night room tariff and taxes (12% GST standard), records advance deposit, and prints or WhatsApps registration receipt.
- Mid-stay charges (extra bed, room service, laundry) post as line-item debits to the guest folio.
- Check-out settlement reconciles total debits against credits, captures final settlement payment, and prints GST tax invoice.

### 10.2 Digital Self-Service Portal (`/checkin/[token]`)
- Arriving guests receive a secure, short-lived tokenized link via WhatsApp or SMS.
- Mobile-first interface greets the guest with hotel branding, room category, and check-in instructions.
- Guest submits full name, phone, address, and selects Government ID type (Driving License, Passport, Voter ID, Aadhaar).
- **Indian DPDP Act 2023 Compliance**:
  - Raw 12-digit Aadhaar numbers and unrestricted Aadhaar card photos are **never stored**.
  - Client-side and backend masks ID numbers to the last 4 digits (e.g., `XXXXXXXX4321`).
  - Guest documents uploaded to private storage buckets are accessible only by authorized Manager/Owner roles and undergo automatic 30-day purge cycles.

---

## 11. Financial Management & Accounting

### 11.1 Segregated Financial Ledgers
1. **Earned Revenue Ledger (Accrual)**: Nightly posted room tariffs, extra amenities, and food charges.
2. **Collections Ledger (Cash Flow)**: Cash drawer, UPI receipts, POS terminal card slips, and bank transfers.
3. **Accounts Receivable (Guest Folio)**: Unsettled ledger balances for active in-house guests.
4. **Operating Expense Ledger**: Property vouchers categorized by department, vendor, payment mode, and invoice receipt attachment.

### 11.2 Expense Categories & Allocation Rules
- Categories: Electricity & Power, Water Supply, Housekeeping Consumables, Linen Purchases, Appliance Repairs, Staff Salaries, Property Lease/Rent, Vendor Laundry Services.
- **Allocation Basis**:
  - `DIRECT`: Explicitly assigned to a single room (e.g., replacing Room 203 TV screen).
  - `EQUAL_PER_ROOM`: Shared facility costs distributed evenly across all sellable keys.
  - `OCCUPIED_ROOM_NIGHTS`: Variable utility costs distributed based on weighted occupied room-days.

### 11.3 Night Audit Engine
- Executes daily at the property's configured reporting cutoff (default `23:59:00 Asia/Kolkata`).
- **Processing Steps**:
  1. Acquires database-level advisory lock (`pg_advisory_xact_lock`) to prevent concurrent duplicate runs.
  2. Identifies all active `CHECKED_IN` stays and posts room tariff revenue and applicable GST for the business date.
  3. Updates stay folio balances (`total_room_charge`, `total_tax`, `balance_due`).
  4. Aggregates daily KPIs: Occupied rooms, Vacant rooms, ADR, RevPAR, Operating Contribution, Cash Collections, Expenses, and Discrepancies.
  5. Commits daily snapshot to `generated_reports` table.
  6. Dispatches executive digest to Owner WhatsApp and Email.

---

## 12. Utilities & Energy Management

Given the commercial power tariffs in Uttar Pradesh, utility monitoring directly impacts bottom-line viability.

### 12.1 Meter Architecture & Readings
- **Master Meters**: Commercial Electricity (UPPCL) and Commercial Water / Tube-well pump meters.
- **Sub-Meters**: Dedicated IoT or digital sub-meters installed on specific high-consumption rooms or floors.
- **Reading Protocol**: Staff log reading date, meter dial value, and invoice attachments.
- **Labeling Standard**: Every utility reading and cost is explicitly labeled:
  - `MEASURED`: Directly read from an isolated room sub-meter.
  - `ALLOCATED`: Derived from property master meter based on occupied room-nights.
  - `ESTIMATED`: Projected based on historical seasonal averages.

---

## 13. Vendor & Procurement Management

### 13.1 Purchase Orders & 3-Way Matching
- Maintain verified vendor database (laundry contractors, linen distributors, beverage suppliers, electricians).
- Create Purchase Orders (PO) with itemized quantities, agreed unit rates, and expected delivery dates.
- Goods Received Notes (GRN) verify incoming physical quantities against the PO.
- Supplier invoices reconcile against GRN quantities before payment release, preventing overbilling and duplicate invoice entry.

---

## 14. Automated Daily Reporting

Every hotel owner receives a consolidated daily performance digest at their configured reporting time (default `23:59 Asia/Kolkata`).

### 14.1 Delivery Channels
- **Meta WhatsApp Business Cloud API**: Delivers executive text summary and download link for high-resolution PDF report.
- **Transactional Email (Resend / AWS SES)**: Full HTML performance digest with attached PDF report.
- **In-App Archive**: Historical daily and monthly reports searchable by date.

### 14.2 Report Contents
1. **Occupancy Summary**: Total keys, occupied keys, clean keys, dirty keys, maintenance blocked keys, occupancy rate %.
2. **Financial Performance**: Accrual earned revenue, cash collections received, expenses recorded, operating contribution (GOP).
3. **Operational Queues**: Pending maintenance tickets, pending housekeeping tasks, damaged or missing assets.
4. **Historical Comparison**: Day-over-day and month-to-date trajectory.

---

## 15. Grounded AI Hotel Assistant

The AI Assistant allows hotel owners and managers to query live property records in natural language.

### 15.1 Architectural Guardrails
- **Zero Raw SQL Execution**: The LLM is completely barred from generating or executing raw SQL queries against the database.
- **Deterministic Tool Calling**: The assistant interacts strictly through a whitelist of typed, parameter-verified backend functions (`get_daily_occupancy_metrics`, `get_revenue_metrics`, `get_asset_discrepancies`, `get_maintenance_summary`, `get_low_stock_categories`).
- **Session-Injected Tenant Context**: The active `hotel_id` and user role are automatically injected into tool executions from the authenticated session, preventing cross-tenant data leakage.
- **Fact Grounding**: If data is missing or unavailable, the assistant explicitly states the absence of records rather than hallucinating answers.

