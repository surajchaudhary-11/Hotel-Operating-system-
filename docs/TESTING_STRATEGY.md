# HotelOS — Comprehensive Testing Strategy & Quality Assurance Blueprint
**Version:** 1.0.0-PROD  
**Target Platform:** Multi-Tenant Hospitality Operating System  
**Test Frameworks:** Pytest / Pytest-Asyncio (Backend), Playwright / Jest (Frontend)

---

## 1. Testing Philosophy & Quality Gateways

HotelOS manages real-world hospitality transactions, room inventories, and legal financial records. Reliability, zero double-bookings, and ironclad tenant isolation are mission-critical.

### Quality Gate Hierarchy:
1. **Static Analysis & Type Checking:**
   - Backend: `mypy --strict app`, `ruff check app`
   - Frontend: `tsc --noEmit`, `eslint .`
2. **Unit Tests:** Fast, isolated testing of pure business logic (financial formulas, masking, ledger balance math, scenario modeling).
3. **Integration & API Tests:** End-to-end route tests using an async in-memory SQLite / test PostgreSQL database.
4. **Security & Penetration Tests:** Explicit tests attempting cross-tenant leakage, role privilege escalation, and SQL injection.
5. **Concurrency & Race Condition Tests:** Simulating parallel front-desk requests (e.g. two receptionists booking the same room at the same millisecond).

---

## 2. Test Suite Architecture

```
hotel/
├── backend/
│   ├── pytest.ini
│   ├── tests/
│   │   ├── conftest.py             # Fixtures: async db, test hotels, JWT generators, tenant headers
│   │   ├── test_api.py             # Core API route integration tests
│   │   ├── test_accounting.py      # USALI financial formula & ADR/RevPAR validation
│   │   ├── test_inventory_ledger.py# Double-entry movement & overdraft guard tests
│   │   ├── test_security_rbac.py   # Cross-tenant & role privilege escalation tests
│   │   ├── test_concurrency.py     # Parallel check-in and double-booking prevention
│   │   └── test_night_audit.py     # Audit execution and idempotency verification
├── frontend/
│   ├── __tests__/
│   │   ├── components/             # Unit tests for UI components (Checklist, Forms, Badges)
│   │   └── e2e/                    # Playwright end-to-end guest journey workflows
```

---

## 3. Ten Critical Business Test Scenarios

### Scenario 1: Concurrent Check-In on Same Room (Double-Booking Prevention)
- **Objective:** Ensure two simultaneous check-in attempts on the same room result in exactly one successful check-in and one rejected with `400 Bad Request`.
- **Precondition:** Room 101 is `VACANT_CLEAN`.
- **Execution:** Dispatch two concurrent async HTTP POST requests to `/api/v1/guests/check-in` for Room 101 with distinct guest IDs.
- **Expected Outcome:**
  - First request: `HTTP 200 OK`, stay created, room marked `OCCUPIED`.
  - Second request: `HTTP 400 Bad Request` (`"Room 101 is currently OCCUPIED"`). No duplicate stay created.

---

### Scenario 2: Cross-Tenant Data Access Attempt (Tenant Isolation)
- **Objective:** Verify a user authenticated in Hotel A cannot view, query, or mutate records belonging to Hotel B.
- **Precondition:** User A is `OWNER` of Hotel A (`h-01`). Room 201 belongs to Hotel B (`h-02`).
- **Execution:** User A sends `GET /api/v1/rooms` with header `X-Hotel-ID: h-02`.
- **Expected Outcome:** `HTTP 403 Forbidden` (`"User does not have active membership in this hotel"`). Zero rows from Hotel B are exposed.

---

### Scenario 3: Inventory Negative Balance / Overdraft Prevention
- **Objective:** Verify that issuing more inventory items than available stock at a location is rejected.
- **Precondition:** Category "Bath Towel" has 10 units in `STORAGE`.
- **Execution:** Post transaction `ISSUE_TO_ROOM` with quantity 15 from `STORAGE` to `ROOM`.
- **Expected Outcome:** Transaction rejected with `HTTP 400 Bad Request` (`"Insufficient inventory: 10 available, 15 requested"`). Ledger balance remains exactly 10.

---

### Scenario 4: Maintenance Ticket Auto-Block & Unblock Lifecycle
- **Objective:** Verify that a critical maintenance ticket automatically blocks the room from guest sales, and resolving the ticket returns the room to dirty status for cleaning.
- **Precondition:** Room 104 is `VACANT_CLEAN`.
- **Execution:**
  1. Post maintenance ticket on Room 104 with priority `CRITICAL`.
  2. Inspect Room 104 status.
  3. Post update resolving the ticket (`status_change = "RESOLVED"`).
  4. Inspect Room 104 status.
- **Expected Outcome:**
  - After step 1: Room 104 status is `BLOCKED_MAINTENANCE`.
  - After step 3: Ticket status is `RESOLVED`; Room 104 status becomes `VACANT_DIRTY` (requiring cleaning before it can be sold).

---

### Scenario 5: Housekeeping Task to Inspection to Clean Transition
- **Objective:** Ensure a room cannot be marked `VACANT_CLEAN` until all 5 checklist items are completed and a supervisor submits a passing inspection.
- **Precondition:** Room 102 is `VACANT_DIRTY`.
- **Execution:**
  1. Attendant completes 4 of 5 checklist items and attempts to finalize task.
  2. Attendant completes remaining item and submits.
  3. Supervisor submits `PASSED` inspection.
- **Expected Outcome:**
  - Step 1: Rejected or flagged incomplete.
  - Step 2: Task moves to `INSPECTION_PENDING`; room remains `INSPECTION_PENDING`.
  - Step 3: Room status transitions to `VACANT_CLEAN`.

---

### Scenario 6: Night Audit Tariff Posting Idempotency
- **Objective:** Ensure re-running the Night Audit multiple times on the same calendar night does not duplicate room tariff revenue or double-bill guests.
- **Precondition:** Stay #501 is checked in at ₹3,500/night.
- **Execution:**
  1. Trigger Night Audit for date `2026-10-31`.
  2. Verify revenue entries for Stay #501 on `2026-10-31`.
  3. Trigger Night Audit again for date `2026-10-31`.
  4. Verify revenue entries and total audit summary.
- **Expected Outcome:** Exactly one revenue record of ₹3,500 exists. The second execution updates the existing summary record with identical financial figures.

---

### Scenario 7: Digital Self-Check-in Token Invalidation
- **Objective:** Ensure a guest digital check-in token cannot be reused after registration has been completed.
- **Precondition:** Stay #601 has token `abc123xyz...`.
- **Execution:**
  1. Submit guest details via `/api/v1/guests/digital-checkin/abc123xyz.../submit`.
  2. Front Desk marks stay as `CHECKED_IN`.
  3. Attempt a second submission using the same token.
- **Expected Outcome:** Second request returns `HTTP 400 Bad Request` or `HTTP 404 Not Found` (`"Invalid or expired registration link"`).

---

### Scenario 8: Role Escalation Attack Prevention (Receptionist viewing Owner Finance)
- **Objective:** Verify a user with `RECEPTIONIST` role cannot access executive financial summaries or room profitability calculations.
- **Precondition:** User is logged in as `RECEPTIONIST` in Hotel A.
- **Execution:** Send `GET /api/v1/finance/summary` and `GET /api/v1/finance/room-profitability`.
- **Expected Outcome:** Both requests return `HTTP 403 Forbidden` (`"Insufficient permissions: Role RECEPTIONIST is not authorized"`).

---

### Scenario 9: Aadhaar Masking & Plain-Text Leak Prevention
- **Objective:** Ensure full 12-digit Aadhaar numbers are never returned in guest responses or stored in plain text.
- **Execution:**
  1. Register guest with Aadhaar `5678 1234 9012`.
  2. Query guest details via `GET /api/v1/guests/stays`.
  3. Directly inspect the database row in `guests`.
- **Expected Outcome:**
  - API response displays `XXXXXXXX9012`.
  - Database column `id_number_masked` contains `XXXXXXXX9012`. Raw 12-digit string exists nowhere in storage.

---

### Scenario 10: Room Profitability Calculation Accuracy (Direct vs. Allocated Costs)
- **Objective:** Verify mathematical correctness of month-to-date room operating contribution.
- **Precondition:**
  - Room 101 generated ₹35,000 in revenue this month.
  - Direct maintenance costs for Room 101 = ₹2,500.
  - Property shared expenses = ₹20,000 across 20 rooms (₹1,000/room).
- **Execution:** Call `GET /api/v1/finance/room-profitability`.
- **Expected Outcome:**
  - Room 101 Total Cost = $₹2,500 + ₹1,000 = ₹3,500$.
  - Operating Contribution = $₹35,000 - ₹3,500 = ₹31,500$.
  - Contribution Margin = $\left( \frac{31,500}{35,000} \right) \times 100 = 90.0\%$.

---

## 4. Test Execution Instructions

### Running Backend Pytest Suite
```bash
# Activate virtual environment
cd backend
source venv/Scripts/activate  # On Windows: .\venv\Scripts\Activate.ps1

# Run full test suite with verbose output
pytest -v

# Run with test coverage report
pytest --cov=app --cov-report=term-missing tests/
```

### Running Frontend Validation
```bash
cd frontend

# Type-check TypeScript code
npm run build

# Run linting
npm run lint
```

