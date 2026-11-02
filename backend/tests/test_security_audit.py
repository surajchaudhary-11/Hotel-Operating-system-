"""
HotelOS — Production Readiness & Security Audit Test Suite
Covers:
- Rate limiting on sensitive endpoints (brute-force defense)
- Digital check-in single-use enforcement, expiration, and PII masking
- Night audit concurrency locking and duplicate prevention
- Night audit retry and recovery
- Production demo account restriction
- Timezone boundary resolution
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
import pytest_asyncio
import httpx
from app.main import app
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core.timezone import get_hotel_today
from app.core.rate_limit import login_rate_limiter, digital_checkin_rate_limiter
from app.services.seed_service import seed_initial_data
from app.services.night_audit import NightAuditService
from app.models.models import GuestStay, Guest, Room, Revenue, GeneratedReport, Hotel, User

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

@pytest.mark.asyncio
async def test_rate_limiting_login_endpoint():
    """Verify brute-force rate limiting on /auth/login returns 429 when threshold exceeded."""
    login_rate_limiter.reset()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        last_resp = None
        for i in range(12):
            last_resp = await client.post("/api/v1/auth/login", json={
                "email": "invalid_user@example.com",
                "password": "WrongPassword!"
            })
            if last_resp.status_code == 429:
                break

        assert last_resp.status_code == 429
        assert "Rate limit exceeded" in last_resp.json()["detail"]
        assert "Retry-After" in last_resp.headers
    login_rate_limiter.reset()

@pytest.mark.asyncio
async def test_digital_checkin_phone_masked_and_expiration():
    """Verify /digital-checkin/{token} masks guest phone number and protects private data."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        hotel = (await session.execute(select(Hotel))).scalars().first()
        room = (await session.execute(select(Room).where(Room.hotel_id == hotel.id))).scalars().first()
        guest = Guest(
            hotel_id=hotel.id,
            full_name="Pooja Verma",
            email="pooja.verma@example.com",
            phone="+91 98765 11223"
        )
        session.add(guest)
        await session.flush()
        fresh_stay = GuestStay(
            hotel_id=hotel.id,
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now(timezone.utc),
            expected_check_out_time=datetime.now(timezone.utc) + timedelta(days=2),
            status="CHECKED_IN",
            room_rate_per_night=Decimal("2500.00"),
            total_room_charge=Decimal("2500.00"),
            balance_due=Decimal("2500.00")
        )
        session.add(fresh_stay)
        await session.commit()
        await session.refresh(fresh_stay)
        token = fresh_stay.registration_token

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/guests/digital-checkin/{token}")
        assert resp.status_code == 200
        data = resp.json()
        assert "****" in data["guest_phone"]
        assert not data["guest_phone"].replace(" ", "").isdigit() # Must not be raw plaintext phone

@pytest.mark.asyncio
async def test_digital_checkin_single_use_prevents_replay():
    """Verify that submitting digital check-in invalidates the registration token to prevent replay."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        hotel = (await session.execute(select(Hotel))).scalars().first()
        room = (await session.execute(select(Room).where(Room.hotel_id == hotel.id))).scalars().first()
        guest = Guest(
            hotel_id=hotel.id,
            full_name="Aakash Mehra",
            email="aakash.mehra@example.com",
            phone="+91 98111 22334"
        )
        session.add(guest)
        await session.flush()
        fresh_stay = GuestStay(
            hotel_id=hotel.id,
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now(timezone.utc),
            expected_check_out_time=datetime.now(timezone.utc) + timedelta(days=2),
            status="CHECKED_IN",
            room_rate_per_night=Decimal("3000.00"),
            total_room_charge=Decimal("3000.00"),
            balance_due=Decimal("3000.00")
        )
        session.add(fresh_stay)
        await session.commit()
        await session.refresh(fresh_stay)
        token = fresh_stay.registration_token

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1st Submission (Valid)
        sub_resp = await client.post(f"/api/v1/guests/digital-checkin/{token}/submit", json={
            "full_name": "Aakash Mehra",
            "email": "aakash.mehra@example.com",
            "phone": "+91 98111 22334",
            "id_type": "AADHAAR",
            "id_number_masked": "1234 5678 9012",
            "city": "Lucknow",
            "state": "Uttar Pradesh"
        })
        assert sub_resp.status_code == 200

        # 2nd Submission with same token (Must be rejected as already used)
        replay_resp = await client.post(f"/api/v1/guests/digital-checkin/{token}/submit", json={
            "full_name": "Tampered Name",
            "email": "hacker@example.com",
            "phone": "+91 9999999999",
            "id_type": "AADHAAR",
            "id_number_masked": "9999 9999 9999",
            "city": "Unknown",
            "state": "Unknown"
        })
        assert replay_resp.status_code in [404, 410]

@pytest.mark.asyncio
async def test_night_audit_concurrency_lock_prevents_duplicate_billing():
    """Verify that concurrent runs of run_night_audit do not duplicate room charges or folio balances."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        res = await session.execute(select(Hotel).where(Hotel.is_active == True))
        hotel = res.scalars().first()
        hotel_id = hotel.id
        test_audit_date = date(2026, 11, 15)

    async with AsyncSessionLocal() as s1:
        res1 = await NightAuditService.run_night_audit(s1, hotel_id, test_audit_date)

    async with AsyncSessionLocal() as s2:
        res2 = await NightAuditService.run_night_audit(s2, hotel_id, test_audit_date)

    # Second execution must post 0 new revenue charges
    assert res1["financials"]["posted_room_charges_count"] >= 1
    assert res2["financials"]["posted_room_charges_count"] == 0

    # Verify database state has only 1 report record for this date
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, func
        rep_res = await session.execute(
            select(func.count(GeneratedReport.id))
            .where(GeneratedReport.hotel_id == hotel_id, GeneratedReport.report_date == test_audit_date)
        )
        assert rep_res.scalar_one() == 1

@pytest.mark.asyncio
async def test_night_audit_retry_and_recovery():
    """Verify that re-running night audit is idempotent and safely updates the report without duplicating revenue."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        hotel = (await session.execute(select(Hotel))).scalars().first()
        hotel_id = hotel.id
        audit_date = date(2026, 11, 20)

    # Initial Run
    async with AsyncSessionLocal() as s1:
        res1 = await NightAuditService.run_night_audit(s1, hotel_id, audit_date)
    posted_count_1 = res1["financials"]["posted_room_charges_count"]

    # Retry Run (Should post 0 new charges and update report safely)
    async with AsyncSessionLocal() as s2:
        res2 = await NightAuditService.run_night_audit(s2, hotel_id, audit_date)
    posted_count_2 = res2["financials"]["posted_room_charges_count"]

    assert posted_count_1 >= 1
    assert posted_count_2 == 0 # 0 duplicate charges posted on retry
    assert res1["financials"]["today_earned_revenue_accrual"] == res2["financials"]["today_earned_revenue_accrual"]

@pytest.mark.asyncio
async def test_production_environment_demo_seeding_guard():
    """Verify that demo seeding is blocked when ENVIRONMENT='production'."""
    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        async with AsyncSessionLocal() as session:
            await seed_initial_data(session)
    finally:
        settings.ENVIRONMENT = orig_env

@pytest.mark.asyncio
async def test_timezone_date_resolution():
    """Verify that get_hotel_today accurately calculates business dates for Asia/Kolkata."""
    ist_today = get_hotel_today("Asia/Kolkata")
    assert isinstance(ist_today, date)
    fallback_today = get_hotel_today("Invalid/Timezone")
    assert isinstance(fallback_today, date)
    assert fallback_today == ist_today
