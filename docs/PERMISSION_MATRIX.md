# HotelOS — Role-Based Access Control & Permission Matrix
**Version:** 1.0.0-PROD  
**Specification Standard:** Granular Multi-Tenant RBAC with Attribute/Context Validation  
**Target Platform:** Multi-Tenant Hospitality Operating System

---

## 1. Principles of HotelOS Access Control

1. **Strict Multi-Tenant Scoping (`hotel_id`):**
   Permissions are never granted globally across the platform (except for the internal `ADMIN` platform superuser). Every user's authorization is bound to an active `HotelMembership` record linking `(user_id, hotel_id, role)`. A user may be an `OWNER` of Hotel A, a `MANAGER` of Hotel B, and have no access to Hotel C.
2. **Contextual Enforcement:**
   Every API request evaluates the caller's JWT identity and resolves their effective role inside the specific hotel identified by the `X-Hotel-ID` header. If no active membership exists for that hotel, the request is immediately rejected with `HTTP 403 Forbidden`.
3. **Principle of Least Privilege:**
   Operational front-line workers (housekeeping attendants, maintenance technicians) have mobile-optimized access strictly limited to the tasks and tickets assigned to them or their department.
4. **Data Redaction & Privacy Guardrails:**
   Sensitive guest PII (such as full unmasked Aadhaar numbers) and confidential financial data (such as staff wages or property owner net profit) are redacted at the serializer level based on role hierarchy.

---

## 2. Defined Roles & Personas

| Role Code | Title / Persona | Primary Scope & Responsibility |
|---|---|---|
| `OWNER` | Hotel Proprietor / Managing Director | Complete sovereign authority over property settings, banking, staff hiring/firing, financial ledgers, revenue management, and reporting schedules. |
| `MANAGER` | General Manager / Operations Manager | Day-to-day property operational oversight: room state management, inventory transfers, staff task assignment, housekeeping inspections, maintenance ticket approvals, and operational reports. |
| `RECEPTIONIST` | Front Desk Executive / Reception Staff | Guest arrival and departure operations: guest check-in, identity verification, room assignment, advance & folio payment collection, key issuance, and digital self check-in link generation. |
| `HOUSEKEEPING` | Housekeeper / Floor Attendant | Mobile-first cleaning task execution: checklist item completion, room linen replenishment, reporting room clean status, and flagging damaged assets. |
| `MAINTENANCE` | Maintenance Engineer / Technician | Asset repair tracking: maintenance ticket triage, diagnostic notes, repair photos, spare parts logging, and actual cost tracking. |
| `ACCOUNTANT` | Financial Controller / Bookkeeper | Ledger oversight: recording operating expenses, verifying vendor bills, reviewing Night Audit summaries, GST tax reporting, and room profitability analysis. No front-desk room mutation access. |
| `ADMIN` | Platform Super-Administrator | Multi-tenant SaaS infrastructure administration: tenant onboarding verification, platform health monitoring, cross-hotel subscription billing, and audit logs. |

---

## 3. Comprehensive RBAC Matrix

### Legend
- `C` = Create / Insert
- `R` = Read / View
- `U` = Update / Edit
- `D` = Delete / Soft-Delete
- `A` = Approve / Authorize / Close
- `X` = Denied / No Access
- `*` = Restricted to self-assigned records only

| Functional Resource / Domain | OWNER | MANAGER | RECEPTIONIST | HOUSEKEEPING | MAINTENANCE | ACCOUNTANT | ADMIN |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Property Profile & Legal Settings** | CRUD | R | R | X | X | R | CRUD |
| **Staff Memberships & Role Assignment** | CRU | R | X | X | X | X | CRUD |
| **Floors & Room Master Setup** | CRUD | CRU | R | R | R | R | CRUD |
| **Room Housekeeping Status Override** | CRU | CRU | CRU | U* | U* | R | CRUD |
| **Room 360 Inspection Details** | CRUD | CRUD | R | R* | R* | R | CRUD |
| **Asset Master Registry** | CRUD | CRU | R | R | CRU | R | CRUD |
| **QR Code Generation & Printing** | CRU | CRU | R | X | R | X | CRUD |
| **Inventory Ledger Transactions** | CRU | CRU | R | C* | C* | R | CRUD |
| **Physical Inventory Audits** | CRUA | CRUA | R | C* | C* | R | CRUD |
| **Housekeeping Task Creation & Assign** | CRUD | CRUD | CR | X | X | X | CRUD |
| **Housekeeping Checklist Execution** | CRU | CRU | R | U* | X | X | CRUD |
| **Supervisor Room Clean Inspection** | CRA | CRA | X | X | X | X | CRUD |
| **Maintenance Ticket Creation** | CRUD | CRUD | CR | CR | CRUD | R | CRUD |
| **Maintenance Resolution & Cost Entry** | CRUA | CRUA | R | X | CRU | R | CRUD |
| **Laundry Vendor Configuration** | CRUD | CRU | R | X | X | R | CRUD |
| **Laundry Dispatch & Return Recording** | CRU | CRU | CRU | C* | X | R | CRUD |
| **Guest Profile & Stays Master** | CRUD | CRU | CRUD | R | R | R | CRUD |
| **Guest Check-In & Check-Out** | CRUA | CRUA | CRUA | X | X | X | CRUD |
| **Guest Identity Document Viewing** | R | R | R | X | X | X | CRUD |
| **Digital Check-In Token Generation** | CRU | CRU | CRU | X | X | X | CRUD |
| **Revenue & Folio Ledger Entries** | CRUA | CRU | CR | X | X | RU | CRUD |
| **Payment Collection (Cash/UPI/POS)** | CRUA | CRUA | CR | X | X | RU | CRUD |
| **Operating Expenses & Vouchers** | CRUA | CRUA | X | X | C* | CRUA | CRUD |
| **Room-Wise Profitability Dashboard** | R | R | X | X | X | R | CRUD |
| **What-If Scenario Simulation** | R | R | X | X | X | R | CRUD |
| **Utility Meters & Consumption Logs** | CRUD | CRU | R | X | CRU | R | CRUD |
| **Manual Night Audit Execution** | A | A | X | X | X | X | A |
| **Daily Night Audit Summary View** | R | R | R | X | X | R | CRUD |
| **Night Audit Executive PDF Export** | R | R | X | X | X | R | CRUD |
| **Automated Dispatch Settings** | CRU | R | X | X | X | X | CRUD |
| **AI Assistant: Operational Queries** | Full | Full | FrontDesk | MyTasks | MyTickets | Finance | Full |
| **AI Assistant: Financial & Profitability**| Full | Full | Denied | Denied | Denied | Full | Full |

---

## 4. Field-Level Redaction & Privacy Specifications

### 4.1 Guest Identity Documents (Indian DPDP Act 2023 Compliance)
- **Aadhaar Numbers:**
  - Raw 12-digit Aadhaar numbers are **never stored** in plain text.
  - The database stores only the masked value `XXXXXXXX9012` and a SHA-256 HMAC hash for deduplication.
  - Front Desk staff and Managers see only `XXXXXXXX9012`.
  - Housekeeping, Maintenance, and external vendors have zero read access to any identity document attributes.
- **Physical ID Scans & Photos:**
  - Stored in private Supabase Storage buckets with server-signed URLs expiring after 15 minutes.
  - Accessible only to `OWNER`, `MANAGER`, and `RECEPTIONIST`.

### 4.2 Financial Redaction
- **Staff Wages & Owner Drawings:**
  - Visible only to `OWNER` and `ACCOUNTANT`.
  - Hidden from `MANAGER` and `RECEPTIONIST` on all financial dashboards and AI tool queries.
- **Room Operating Contribution:**
  - Visible to `OWNER`, `MANAGER`, and `ACCOUNTANT`.
  - Hidden from `RECEPTIONIST`, `HOUSEKEEPING`, and `MAINTENANCE`.

---

## 5. Multi-Hotel Switching Architecture

When a single user holds memberships across multiple properties:
1. `GET /api/v1/auth/me` returns an array of authorized hotels with role descriptors:
   ```json
   "memberships": [
     {"hotel_id": "h-01", "hotel_name": "Kashi Heritage Haveli", "role": "OWNER"},
     {"hotel_id": "h-02", "hotel_name": "Ganga View Residency", "role": "MANAGER"}
   ]
   ```
2. The frontend stores the user's active property in browser session state and emits the active `hotel_id` as the `X-Hotel-ID` header on every subsequent request.
3. The backend dependency `get_tenant_context` retrieves the membership record for `(current_user.id, X-Hotel-ID)`:
   - If no record exists, raises `HTTP 403 Forbidden` ("You do not have active membership in this hotel").
   - If the membership exists, binds the resolved role to `TenantContext.role`.
4. Role checks via `require_roles(["OWNER", "MANAGER"])` validate the caller's specific role for that hotel. Switching hotels immediately alters the caller's permissions to match their role in the selected property.

