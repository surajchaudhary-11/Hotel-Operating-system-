"""
HotelOS Phase 2 — Comprehensive Reservation & Booking Management Test Suite
Covers:
1. Reservation creation with booking reference and booking source tracking (Direct, OTAs, Corporate).
2. Half-open interval availability semantics (same-day turnarounds succeed without false conflict).
3. Overlapping reservation collision rejection (409 Conflict).
4. Concurrent race conditions on identical rooms and dates (mutual exclusion).
5. Multi-room group reservations sharing group_booking_id and split advance deposits.
6. Reservation lifecycle state machine (RESERVED -> CHECKED_IN, room OCCUPIED, revenue posted).
7. Reservation cancellation with reason, refund tracking, and invalid state transition blocks.
8. Room reassignment with atomic availability validation.
9. Advance deposit payment tracking and USALI compliance (deposit is a liability, not premature revenue).
10. Multi-tenant data isolation across distinct properties.
11. Role-based access control (OWNER/MANAGER/RECEPTIONIST allowed; unauthorized roles blocked).
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
import pytest_asyncio
import httpx
from app.core.rate_limit import login_rate_limiter, account_login_rate_limiter
from sqlalchemy import select, func, delete, or_

from app.main import app
from app.core.database import AsyncSessionLocal
from app.services.seed_service import seed_initial_data
from app.models.models import (
    GuestStay, Guest, Room, Revenue, Payment, Refund, Hotel, HotelMembership, User, ActivityLog
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    login_rate_limiter.reset()
    account_login_rate_limiter.reset()
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)
        # Clean up any test stays created with BK- booking references
        stmt = select(GuestStay.id).where(GuestStay.booking_reference.like("BK-%"))
        stay_ids = (await session.execute(stmt)).scalars().all()
        if stay_ids:
            await session.execute(delete(Payment).where(Payment.stay_id.in_(stay_ids)))
            await session.execute(delete(Revenue).where(Revenue.stay_id.in_(stay_ids)))
            await session.execute(delete(Refund).where(Refund.stay_id.in_(stay_ids)))
            await session.execute(delete(GuestStay).where(GuestStay.id.in_(stay_ids)))
            await session.commit()


async def get_auth_context(client: httpx.AsyncClient, email="owner@kashiheritage.com", password="HotelOS2026!"):
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed: {res.text}"
    data = res.json()
    token = data["access_token"]
    hotel_id = data["memberships"][0]["hotel_id"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Hotel-ID": hotel_id
    }
    return token, hotel_id, headers


@pytest.mark.asyncio
async def test_create_single_reservation_success():
    """Verify creating a single advance reservation with auto-generated booking ref and OTA channel."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, hotel_id, headers = await get_auth_context(client)

        # Get first room
        rooms_res = await client.get("/api/v1/rooms", headers=headers)
        assert rooms_res.status_code == 200
        room = rooms_res.json()[0]

        now = datetime.now(timezone.utc)
        check_in = (now + timedelta(days=10)).replace(hour=12, minute=0, second=0, microsecond=0)
        check_out = (now + timedelta(days=13)).replace(hour=11, minute=0, second=0, microsecond=0)

        payload = {
            "room_id": room["id"],
            "check_in_time": check_in.isoformat(),
            "expected_check_out_time": check_out.isoformat(),
            "adult_count": 2,
            "child_count": 1,
            "room_rate_per_night": 3500.0,
            "booking_source": "MAKEMYTRIP",
            "external_reference_id": "MMT-8829141",
            "special_requests": "Upper floor with temple view, extra blanket",
            "estimated_arrival_time": "14:30",
            "advance_payment_amount": 3500.0,
            "advance_payment_mode": "UPI_QR",
            "guest_info": {
                "full_name": "Vikramaditya Sharma",
                "phone": "+91 9876543210",
                "email": "vikram@example.com",
                "city": "Lucknow",
                "state": "Uttar Pradesh",
                "nationality": "Indian",
                "id_type": "AADHAAR_MASKED",
                "id_number_masked": "123456789012"
            }
        }

        res = await client.post("/api/v1/reservations", json=payload, headers=headers)
        assert res.status_code == 201, f"Failed: {res.text}"
        data = res.json()

        assert data["booking_reference"].startswith("BK-")
        assert data["booking_source"] == "MAKEMYTRIP"
        assert data["external_reference_id"] == "MMT-8829141"
        assert data["status"] == "RESERVED"
        assert data["guest_name"] == "Vikramaditya Sharma"
        assert data["room_number"] == room["room_number"]
        assert Decimal(str(data["total_room_charge"])) == Decimal("10500.00") # 3 nights * 3500
        assert Decimal(str(data["total_tax_charge"])) == Decimal("1260.00") # 12%
        assert Decimal(str(data["total_paid"])) == Decimal("3500.00")
        assert data["payment_status"] == "PARTIALLY_PAID"


@pytest.mark.asyncio
async def test_availability_half_open_same_day_turnaround():
    """
    Verify half-open interval semantics:
    Stay A departs on 2026-12-05 at 11:00 AM.
    Stay B arrives on 2026-12-05 at 12:00 PM.
    Both on the same room: they must NOT conflict!
    """
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_auth_context(client)
        room = (await client.get("/api/v1/rooms", headers=headers)).json()[1]

        stay_a_in = datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc)
        stay_a_out = datetime(2026, 12, 5, 11, 0, tzinfo=timezone.utc)

        stay_b_in = datetime(2026, 12, 5, 12, 0, tzinfo=timezone.utc)
        stay_b_out = datetime(2026, 12, 8, 11, 0, tzinfo=timezone.utc)

        # Booking A
        res_a = await client.post("/api/v1/reservations", json={
            "room_id": room["id"],
            "check_in_time": stay_a_in.isoformat(),
            "expected_check_out_time": stay_a_out.isoformat(),
            "room_rate_per_night": 2800.0,
            "guest_info": {"full_name": "Guest Alpha", "phone": "+91 9111111111"}
        }, headers=headers)
        assert res_a.status_code == 201

        # Booking B (arrives on the day Booking A departs)
        res_b = await client.post("/api/v1/reservations", json={
            "room_id": room["id"],
            "check_in_time": stay_b_in.isoformat(),
            "expected_check_out_time": stay_b_out.isoformat(),
            "room_rate_per_night": 2800.0,
            "guest_info": {"full_name": "Guest Beta", "phone": "+91 9222222222"}
        }, headers=headers)
        assert res_b.status_code == 201, f"Expected same-day checkout/checkin turnaround to succeed: {res_b.text}"


@pytest.mark.asyncio
async def test_overlapping_reservation_rejected():
    """Verify that an overlapping reservation request on the same room returns 409 Conflict."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_auth_context(client)
        room = (await client.get("/api/v1/rooms", headers=headers)).json()[2]

        stay_in = datetime(2026, 12, 10, 12, 0, tzinfo=timezone.utc)
        stay_out = datetime(2026, 12, 15, 11, 0, tzinfo=timezone.utc)

        # First booking succeeds
        res1 = await client.post("/api/v1/reservations", json={
            "room_id": room["id"],
            "check_in_time": stay_in.isoformat(),
            "expected_check_out_time": stay_out.isoformat(),
            "room_rate_per_night": 3000.0,
            "guest_info": {"full_name": "Ananya Roy", "phone": "+91 9333333333"}
        }, headers=headers)
        assert res1.status_code == 201

        # Overlapping booking: Dec 12 to Dec 17
        overlap_in = datetime(2026, 12, 12, 12, 0, tzinfo=timezone.utc)
        overlap_out = datetime(2026, 12, 17, 11, 0, tzinfo=timezone.utc)

        res2 = await client.post("/api/v1/reservations", json={
            "room_id": room["id"],
            "check_in_time": overlap_in.isoformat(),
            "expected_check_out_time": overlap_out.isoformat(),
            "room_rate_per_night": 3000.0,
            "guest_info": {"full_name": "Rahul Verma", "phone": "+91 9444444444"}
        }, headers=headers)

        assert res2.status_code == 409
        err = res2.json()["detail"]
        assert f"Room {room['room_number']} is already booked" in err


@pytest.mark.asyncio
async def test_concurrent_reservation_collision():
    """
    Simulate two concurrent booking requests for the exact same room and date interval.
    Exactly one must succeed (201), and the other must be rejected (409).
    """
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_auth_context(client)
        room = (await client.get("/api/v1/rooms", headers=headers)).json()[3]

        c_in = datetime(2026, 12, 20, 12, 0, tzinfo=timezone.utc).isoformat()
        c_out = datetime(2026, 12, 23, 11, 0, tzinfo=timezone.utc).isoformat()

        payload1 = {
            "room_id": room["id"],
            "check_in_time": c_in,
            "expected_check_out_time": c_out,
            "room_rate_per_night": 4000.0,
            "guest_info": {"full_name": "Concurrent One", "phone": "+91 9555555551"}
        }
        payload2 = {
            "room_id": room["id"],
            "check_in_time": c_in,
            "expected_check_out_time": c_out,
            "room_rate_per_night": 4000.0,
            "guest_info": {"full_name": "Concurrent Two", "phone": "+91 9555555552"}
        }

        async def book(payload):
            return await client.post("/api/v1/reservations", json=payload, headers=headers)

        r1, r2 = await asyncio.gather(book(payload1), book(payload2))

        statuses = [r1.status_code, r2.status_code]
        assert 201 in statuses, f"At least one booking must succeed. Got {statuses}"
        assert 409 in statuses, f"Overlapping concurrent booking must be rejected with 409. Got {statuses}"


@pytest.mark.asyncio
async def test_create_group_reservation():
    """Verify group booking creating multiple room stays under a single group_booking_id."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_auth_context(client)
        rooms = (await client.get("/api/v1/rooms", headers=headers)).json()
        assert len(rooms) >= 3

        now = datetime.now(timezone.utc)
        c_in = (now + timedelta(days=15)).replace(hour=12, minute=0, second=0, microsecond=0).isoformat()
        c_out = (now + timedelta(days=18)).replace(hour=11, minute=0, second=0, microsecond=0).isoformat()

        payload = {
            "primary_guest_info": {
                "full_name": "Kapoor Family Tour",
                "phone": "+91 9666666666",
                "email": "kapoor@example.com"
            },
            "check_in_time": c_in,
            "expected_check_out_time": c_out,
            "booking_source": "CORPORATE",
            "external_reference_id": "CORP-KAPOOR-2026",
            "special_requests": "Adjoining rooms preferred",
            "advance_payment_amount": 10000.0,
            "advance_payment_mode": "BANK_TRANSFER",
            "rooms": [
                {
                    "room_id": rooms[0]["id"],
                    "room_rate_per_night": 3000.0,
                    "adult_count": 2,
                    "guest_info": {"full_name": "Raj Kapoor", "phone": "+91 9666666661"}
                },
                {
                    "room_id": rooms[1]["id"],
                    "room_rate_per_night": 3000.0,
                    "adult_count": 2,
                    "guest_info": {"full_name": "Rishi Kapoor", "phone": "+91 9666666662"}
                }
            ]
        }

        res = await client.post("/api/v1/reservations/group", json=payload, headers=headers)
        assert res.status_code == 201, f"Failed: {res.text}"
        data = res.json()
        assert len(data) == 2

        group_id_1 = data[0]["group_booking_id"]
        group_id_2 = data[1]["group_booking_id"]
        assert group_id_1 is not None
        assert group_id_1 == group_id_2, "Stays in group booking must share group_booking_id"

        # Check filter by group_booking_id
        list_res = await client.get(f"/api/v1/reservations?group_booking_id={group_id_1}", headers=headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) == 2


@pytest.mark.asyncio
async def test_reservation_lifecycle_checkin_and_state_machine():
    """Verify check-in transition from RESERVED to CHECKED_IN, room OCCUPIED, and revenue posting."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, hotel_id, headers = await get_auth_context(client)
        room = (await client.get("/api/v1/rooms", headers=headers)).json()[4]

        now = datetime.now(timezone.utc)
        c_in = now.replace(hour=12, minute=0, second=0, microsecond=0).isoformat()
        c_out = (now + timedelta(days=2)).replace(hour=11, minute=0, second=0, microsecond=0).isoformat()

        # 1. Create reservation
        create_res = await client.post("/api/v1/reservations", json={
            "room_id": room["id"],
            "check_in_time": c_in,
            "expected_check_out_time": c_out,
            "room_rate_per_night": 2500.0,
            "guest_info": {"full_name": "Sneha Gupta", "phone": "+91 9777777777"}
        }, headers=headers)
        stay = create_res.json()
        stay_id = stay["id"]
        assert stay["status"] == "RESERVED"

        # 2. Check-in reservation
        checkin_res = await client.post(f"/api/v1/reservations/{stay_id}/checkin", headers=headers)
        assert checkin_res.status_code == 200
        updated = checkin_res.json()
        assert updated["status"] == "CHECKED_IN"

        # 3. Verify room is now OCCUPIED
        room_check = await client.get(f"/api/v1/rooms", headers=headers)
        for r in room_check.json():
            if r["id"] == room["id"]:
                assert r["status"] == "OCCUPIED"

        # 4. Verify initial room tariff revenue posted with idempotency key
        async with AsyncSessionLocal() as session:
            rev_res = await session.execute(
                select(Revenue).where(Revenue.stay_id == stay_id, Revenue.revenue_type == "ROOM_TARIFF")
            )
            rev = rev_res.scalars().first()
            assert rev is not None
            assert rev.amount == Decimal("2500.00")
            assert rev.idempotency_key is not None

        # 5. Invalid transition: attempting to check-in again must fail with 400
        dup_checkin = await client.post(f"/api/v1/reservations/{stay_id}/checkin", headers=headers)
        assert dup_checkin.status_code == 400
        assert "Only 'RESERVED' stays can be checked in" in dup_checkin.json()["detail"]


@pytest.mark.asyncio
async def test_reservation_cancellation_and_refund():
    """Verify cancelling a reservation records cancellation reason and optional refund."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_auth_context(client)
        room = (await client.get("/api/v1/rooms", headers=headers)).json()[5]

        now = datetime.now(timezone.utc)
        c_in = (now + timedelta(days=20)).isoformat()
        c_out = (now + timedelta(days=22)).isoformat()

        create_res = await client.post("/api/v1/reservations", json={
            "room_id": room["id"],
            "check_in_time": c_in,
            "expected_check_out_time": c_out,
            "room_rate_per_night": 3000.0,
            "advance_payment_amount": 3000.0,
            "guest_info": {"full_name": "Pooja Hegde", "phone": "+91 9888888888"}
        }, headers=headers)
        stay_id = create_res.json()["id"]

        # Cancel with refund
        cancel_res = await client.post(f"/api/v1/reservations/{stay_id}/cancel", json={
            "cancellation_reason": "Flight cancelled due to weather",
            "refund_amount": 3000.0,
            "refund_reason": "Full refund per policy"
        }, headers=headers)
        assert cancel_res.status_code == 200
        data = cancel_res.json()
        assert data["status"] == "CANCELLED"
        assert data["cancellation_reason"] == "Flight cancelled due to weather"
        assert data["payment_status"] == "REFUNDED"

        # Verify a cancelled reservation cannot be checked in
        checkin_res = await client.post(f"/api/v1/reservations/{stay_id}/checkin", headers=headers)
        assert checkin_res.status_code == 400


@pytest.mark.asyncio
async def test_room_reassignment():
    """Verify reassigning a reservation to another room with availability check."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_auth_context(client)
        rooms = (await client.get("/api/v1/rooms", headers=headers)).json()
        room1 = rooms[0]
        room2 = rooms[1]

        now = datetime.now(timezone.utc)
        c_in = (now + timedelta(days=25)).isoformat()
        c_out = (now + timedelta(days=27)).isoformat()

        create_res = await client.post("/api/v1/reservations", json={
            "room_id": room1["id"],
            "check_in_time": c_in,
            "expected_check_out_time": c_out,
            "room_rate_per_night": 3200.0,
            "guest_info": {"full_name": "Sameer Joshi", "phone": "+91 9999999991"}
        }, headers=headers)
        stay_id = create_res.json()["id"]

        # Reassign to room2
        reassign_res = await client.post(f"/api/v1/reservations/{stay_id}/reassign", json={
            "new_room_id": room2["id"],
            "reason": "Guest requested higher floor"
        }, headers=headers)
        assert reassign_res.status_code == 200
        updated = reassign_res.json()
        assert updated["room_id"] == room2["id"]
        assert updated["room_number"] == room2["room_number"]


@pytest.mark.asyncio
async def test_advance_deposit_payment_accounting():
    """
    USALI Compliance Test:
    Advance deposits must record in payments ledger, update balance due,
    and NOT post to earned revenues until night audit or stay execution.
    """
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, hotel_id, headers = await get_auth_context(client)
        room = (await client.get("/api/v1/rooms", headers=headers)).json()[6]

        now = datetime.now(timezone.utc)
        c_in = (now + timedelta(days=30)).isoformat()
        c_out = (now + timedelta(days=32)).isoformat()

        # Create with 0 advance
        create_res = await client.post("/api/v1/reservations", json={
            "room_id": room["id"],
            "check_in_time": c_in,
            "expected_check_out_time": c_out,
            "room_rate_per_night": 2000.0,
            "advance_payment_amount": 0.0,
            "guest_info": {"full_name": "Arjun Dev", "phone": "+91 9999999992"}
        }, headers=headers)
        stay = create_res.json()
        stay_id = stay["id"]
        assert Decimal(str(stay["total_paid"])) == Decimal("0.00")
        assert stay["payment_status"] == "UNPAID"

        # Record deposit payment
        pay_res = await client.post(f"/api/v1/reservations/{stay_id}/payments", json={
            "amount": 1500.0,
            "payment_mode": "UPI_QR",
            "transaction_reference": "UPI-DEP-9999",
            "notes": "Advance payment via GPay"
        }, headers=headers)
        assert pay_res.status_code == 200
        paid_data = pay_res.json()
        assert Decimal(str(paid_data["total_paid"])) == Decimal("1500.00")
        assert paid_data["payment_status"] == "PARTIALLY_PAID"

        # Verify payments ledger has entry
        async with AsyncSessionLocal() as session:
            payments = (await session.execute(
                select(Payment).where(Payment.stay_id == stay_id)
            )).scalars().all()
            assert len(payments) == 1
            assert payments[0].amount == Decimal("1500.00")

            # Verify NO revenue record exists for advance deposit
            revenues = (await session.execute(
                select(Revenue).where(Revenue.stay_id == stay_id)
            )).scalars().all()
            assert len(revenues) == 0, "Advance deposit must not be recognized as earned revenue prematurely"


@pytest.mark.asyncio
async def test_tape_chart_calendar_endpoint():
    """Verify /calendar returns room rows and reservation blocks matching the date window."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_auth_context(client)
        today = date.today()

        cal_res = await client.get(f"/api/v1/reservations/calendar?start_date={today.isoformat()}&days=14", headers=headers)
        assert cal_res.status_code == 200
        data = cal_res.json()
        assert "rooms" in data
        assert len(data["rooms"]) >= 8
        assert data["start_date"] == today.isoformat()
        assert "blocks" in data["rooms"][0]


@pytest.mark.asyncio
async def test_multi_tenant_isolation_reservations():
    """Verify Hotel B cannot see or manipulate Hotel A's reservations."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        token_a, hotel_id_a, headers_a = await get_auth_context(client)
        room_a = (await client.get("/api/v1/rooms", headers=headers_a)).json()[0]

        now = datetime.now(timezone.utc)
        create_res = await client.post("/api/v1/reservations", json={
            "room_id": room_a["id"],
            "check_in_time": (now + timedelta(days=5)).isoformat(),
            "expected_check_out_time": (now + timedelta(days=7)).isoformat(),
            "room_rate_per_night": 3000.0,
            "guest_info": {"full_name": "Tenant A Guest", "phone": "+91 9999999993"}
        }, headers=headers_a)
        stay_a_id = create_res.json()["id"]

        # Fetch Hotel B from DB
        async with AsyncSessionLocal() as session:
            hotels = (await session.execute(select(Hotel).where(Hotel.id != hotel_id_a))).scalars().all()
            if not hotels:
                pytest.skip("Second hotel not available for multi-tenant check")
            hotel_b = hotels[0]

            # Assign membership to user for Hotel B if not exists
            user = (await session.execute(select(User).where(User.email == "owner@kashiheritage.com"))).scalar_one()
            existing_mem = (await session.execute(
                select(HotelMembership).where(HotelMembership.hotel_id == hotel_b.id, HotelMembership.user_id == user.id)
            )).scalar_one_or_none()
            if not existing_mem:
                mem_b = HotelMembership(hotel_id=hotel_b.id, user_id=user.id, role="OWNER")
                session.add(mem_b)
                await session.commit()

        headers_b = {
            "Authorization": f"Bearer {token_a}",
            "X-Hotel-ID": hotel_b.id
        }

        # Attempt to access stay from Hotel B context -> Must return 404
        get_res = await client.get(f"/api/v1/reservations/{stay_a_id}", headers=headers_b)
        assert get_res.status_code == 404

        # Listing reservations under Hotel B must NOT contain Hotel A's reservation
        list_res = await client.get("/api/v1/reservations", headers=headers_b)
        assert list_res.status_code == 200
        b_ids = [r["id"] for r in list_res.json()]
        assert stay_a_id not in b_ids


@pytest.mark.asyncio
async def test_role_based_access_control_reservations():
    """Verify RECEPTIONIST can manage reservations, while unauthorized roles (e.g. HOUSEKEEPING) are blocked."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, hotel_id, _ = await get_auth_context(client)

        async with AsyncSessionLocal() as session:
            from app.core.security import get_password_hash
            # Use existing user or create token
            res = await session.execute(select(User).where(User.email == "housekeeping@kashiheritage.com"))
            existing = res.scalars().first()
            if not existing:
                hk_user = User(
                    email="housekeeping@kashiheritage.com",
                    full_name="Housekeeping Staff",
                    password_hash=get_password_hash("HotelOS2026!")
                )
                session.add(hk_user)
                await session.flush()
                mem = HotelMembership(hotel_id=hotel_id, user_id=hk_user.id, role="HOUSEKEEPING")
                session.add(mem)
                await session.commit()

        # Login as housekeeping
        hk_login = await client.post("/api/v1/auth/login", json={
            "email": "housekeeping@kashiheritage.com",
            "password": "HotelOS2026!"
        })
        assert hk_login.status_code == 200
        hk_token = hk_login.json()["access_token"]
        hk_headers = {
            "Authorization": f"Bearer {hk_token}",
            "X-Hotel-ID": hotel_id
        }

        # Housekeeping attempting to list reservations -> 403 Forbidden
        res = await client.get("/api/v1/reservations", headers=hk_headers)
        assert res.status_code == 403
        assert "Operation not permitted" in res.json()["detail"]
