# HotelOS — Production-Ready Full-Stack Hotel Management SaaS
**Version:** 1.0.0-PROD  
**Target Market:** Independent & Mid-Sized Hotels in India (Initial Launch: Varanasi, Uttar Pradesh)  
**Architecture:** Zero-Docker Cloud Native (Vercel + Render + Supabase)

---

## 1. Executive Summary

**HotelOS** is a commercial, multi-tenant B2B Hospitality Operating System engineered to replace fragmented physical registers, disconnected spreadsheets, manual calculations, and informal WhatsApp messaging in Indian hotels.

### Core Value Proposition:
- **Unified Property Control:** Single pane of glass for front desk, housekeeping, maintenance, linen custody, utility tracking, and guest management.
- **Strict Multi-Tenant Isolation:** Complete cryptographic isolation between properties using JWT claims, tenant context middleware, and database-level PostgreSQL Row Level Security (RLS).
- **USALI Financial Rigor:** Enforces the Uniform System of Accounts for the Lodging Industry (USALI 11th Edition), calculating real-time Occupancy %, ADR, RevPAR, and **Operating Contribution** (explicitly distinguishing operational margin from corporate Net Profit).
- **Double-Entry Inventory Ledger:** Immutable stock ledger tracking asset movements across rooms, central storage, and external laundry vendors.
- **Automated Night Audit Pipeline:** End-of-day reconciliation executed at 23:59 Asia/Kolkata with automatic PDF generation and WhatsApp/email dispatch.
- **Indian DPDP Act 2023 Compliance:** Automatic Aadhaar digit masking (`XXXXXXXX9012`), HMAC hashing, and 30-day auto-purge for guest identity documents.
- **Deterministic AI Operations Assistant:** Natural language hotel assistant operating strictly through parameterized, tenant-bound Python tools with **zero Text-to-SQL generation**.

---

## 2. Complete Technical Documentation Suite

The complete engineering, operational, and architectural specifications are organized in the `docs/` directory:

| Document | Description | Key Topics Covered |
|---|---|---|
| [**Product Requirements**](file:///c:/Users/lap/Desktop/hotel/docs/PRODUCT_REQUIREMENTS.md) | Exhaustive PRD across all 15 modules | User personas, functional requirements, inputs/outputs, Indian market edge cases |
| [**System Architecture**](file:///c:/Users/lap/Desktop/hotel/docs/SYSTEM_ARCHITECTURE.md) | Full-stack topology & data flows | Next.js App Router, FastAPI ASGI, RLS policies, background scheduler |
| [**Database Design**](file:///c:/Users/lap/Desktop/hotel/docs/DATABASE_DESIGN.md) | Complete PostgreSQL schema & ERD | 32 tables, foreign keys, check constraints, indexes, missing entity roadmap |
| [**API Specification**](file:///c:/Users/lap/Desktop/hotel/docs/API_SPECIFICATION.md) | REST API catalog (OpenAPI aligned) | Endpoints, headers (`X-Hotel-ID`), request/response JSON schemas, error codes |
| [**Permission Matrix**](file:///c:/Users/lap/Desktop/hotel/docs/PERMISSION_MATRIX.md) | Granular multi-tenant RBAC | 7 roles (`OWNER` to `ADMIN`), CRUD permissions, field-level PII redaction |
| [**Business Rules**](file:///c:/Users/lap/Desktop/hotel/docs/BUSINESS_RULES.md) | Accounting formulas & state machines | USALI Operating Contribution, room states, double-entry inventory, night audit |
| [**Security Specification**](file:///c:/Users/lap/Desktop/hotel/docs/SECURITY_SPECIFICATION.md) | Security & compliance architecture | Tenant isolation, Indian DPDP Act 2023 Aadhaar masking, signed S3 URLs |
| [**Testing Strategy**](file:///c:/Users/lap/Desktop/hotel/docs/TESTING_STRATEGY.md) | QA blueprint & automated test suites | 10 critical business test cases, concurrency, race conditions, pytest/coverage |
| [**Deployment Guide**](file:///c:/Users/lap/Desktop/hotel/docs/DEPLOYMENT_GUIDE.md) | Zero-Docker production guide | Vercel (Frontend), Render (Backend), Supabase (Database), env vars matrix |
| [**Phase 0 Architecture**](file:///c:/Users/lap/Desktop/hotel/docs/PHASE_0_ARCHITECTURE.md) | Original approved architectural blueprint | Foundational architectural decisions and architectural design rationale |

---

## 3. Technology Stack

### Frontend Architecture
- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript 5.x / React 18
- **Styling:** Tailwind CSS with shadcn/ui design tokens
- **Data Visualization:** Recharts
- **Icons:** Lucide React
- **Forms & Validation:** React Hook Form, Zod

### Backend Architecture
- **Framework:** FastAPI (ASGI Python 3.12)
- **Data Modeling:** Pydantic v2
- **ORM & Database Client:** SQLAlchemy 2.0 (AsyncIO)
- **Database Migrations:** Alembic
- **PDF Generation Engine:** ReportLab
- **QR Code Engine:** `qrcode` with PIL / Pillow

### Cloud Infrastructure & Deployment (Zero-Docker Mandate)
- **Frontend Hosting:** Vercel Global Edge Network
- **Backend API Hosting:** Render Web Service (FastAPI ASGI with Uvicorn workers)
- **Relational Database:** Supabase Cloud PostgreSQL 15+ (AWS Mumbai `ap-south-1`) with PgBouncer pooler (port 6543)
- **Document & File Storage:** Supabase Storage (Private S3-compatible bucket with 15-minute signed URLs)
- **Identity & Authentication:** Supabase Auth (JWT RS256/HS256)

---

## 4. Local Development Quick-Start

### 4.1 Backend Setup
1. **Navigate to the `backend` directory:**
   ```powershell
   cd backend
   ```
2. **Activate the Python virtual environment:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```
4. **Apply database migrations:**
   ```powershell
   alembic upgrade head
   ```
5. **Start the FastAPI server:**
   ```powershell
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   - Interactive Swagger API Documentation: [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs)
   - Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 4.2 Frontend Setup
1. **Navigate to the `frontend` directory:**
   ```powershell
   cd frontend
   ```
2. **Install npm dependencies:**
   ```powershell
   npm install
   ```
3. **Launch Next.js development server:**
   ```powershell
   npm run dev
   ```
4. Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 5. Seed Credentials for Local Verification

The local database automatically seeds a real Varanasi hotel (*Kashi Heritage Haveli*) with active operational data:

| Field | Demo Credential |
|---|---|
| **Email** | `owner@kashiheritage.com` |
| **Password** | `HotelOS2026!` |
| **Role** | `OWNER` |
| **Hotel Name** | Kashi Heritage Haveli |
| **Location** | Assi Ghat Road, Varanasi, Uttar Pradesh |
| **Data Seeded** | 3 Floors, 8 Rooms in diverse states (Occupied, Clean, Dirty, Maintenance Blocked), Smart TVs, ACs, King Bedsheets, Active Guest Stays, Housekeeping Checklists, Maintenance Tickets, Expenses, Utility Meters |

*(A **"Use Demo Account"** one-click button is available directly on the login screen).*

---

## 6. Functional Navigation & Page Directory

| Web Route | Module Name | Operational Capabilities |
|---|---|---|
| `/overview` | Executive Dashboard | Accrual Revenue, Collections, Operating Contribution, 7-day revenue chart, action alerts. |
| `/rooms` | Room & Floor Matrix | Real-time status badges, floor filters, quick status updates, Room 360° modal. |
| `/inventory` | Assets & Inventory | Asset registry, QR tag preview, double-entry inventory transaction ledger. |
| `/housekeeping` | Housekeeping Operations | Daily cleaning task board, 5-point room checklists, supervisor inspection modal. |
| `/maintenance` | Equipment Maintenance | Breakdown tickets, priority tags, technician notes, repair cost entry, room unblocking. |
| `/laundry` | Linen & Laundry Custody | Linen distribution (Rooms vs. Storage vs. Dhobi), dispatch batches with ledger sync. |
| `/guests` | Guest Front Desk | Walk-in check-in, advance payment, folio settlement check-out, digital check-in links. |
| `/checkin/[token]`| Digital Self Check-In | Mobile guest registration portal with DPDP-compliant Aadhaar masking. |
| `/finance` | Finance & USALI GOP | Accrual vs. Cash Flow, room-by-room ADR, RevPAR, Operating Contribution, Simulator. |
| `/utilities` | Energy & Utilities | Electric & water sub-meters, daily dial readings, kWh consumption tracking. |
| `/reports` | Night Audit & Reports | On-demand Night Audit trigger, high-res PDF generation, WhatsApp schedule settings. |
| `/ai` | AI Operations Assistant | Grounded conversational AI assistant with deterministic tools and tenant isolation. |
| `/settings` | Property & Team Settings | Hotel profile, check-in/out policies, team member invitations with RBAC roles. |

---

## 7. Running the Automated Test Suite

```powershell
cd backend
.\venv\Scripts\pytest -v
```

### Verified Test Coverage:
- `test_health`: Health check and system readiness verification.
- `test_auth_login`: JWT generation, credential verification, and user payload schema.
- `test_tenant_isolation_rooms`: Cryptographic multi-tenant verification ensuring zero cross-tenant leakage.
- `test_night_audit_trigger`: End-of-day tariff posting, financial aggregation, and summary persistence.
- `test_ai_assistant_occupancy_query`: AI assistant tool calling, tenant-bound data retrieval, and grounded response synthesis.
