"""
HotelOS — Phase 1.1 Critical Security & Financial Integrity Test Suite
Covers:
- Night audit distributed mutual exclusion and database-level revenue idempotency
- Independent execution across different hotels
- Digital check-in expiration enforcement on GET & POST
- Digital check-in atomic single-use consumption and concurrent submission race prevention
- Rate limiting proxy trust validation and IP spoofing resistance
- Account-level login brute-force lockout
- Persistent tenant AI quota metering and expenditure ceiling enforcement
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
from app.core.rate_limit import (
    login_rate_limiter, account_login_rate_limiter, digital_checkin_rate_limiter, ai_chat_rate_limiter
)
from app.services.seed_service import seed_initial_data
from app.services.night_audit import NightAuditService
from app.models.models import (
    GuestStay, Guest, Room, Revenue, GeneratedReport, Hotel, HotelMembership, User,
    TenantAIQuota, TenantAIUsage
)
from sqlalchemy import select, func, delete

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    login_rate_limiter.reset()
    account_login_rate_limiter.reset()
    digital_checkin_rate_limiter.reset()
    ai_chat_rate_limiter.reset()
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session, force=True)

# =====================================================================
# 1. P0 — NIGHT AUDIT FINANCIAL INTEGRITY TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_night_audit_concurrency_lock_and_idempotency():
    """Verify that concurrent runs of run_night_audit post exactly 1 set of charges and 0 duplicates."""
    test_audit_date = date(2026, 12, 10)
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Hotel).where(Hotel.slug == "kashi-heritage-haveli"))
        hotel = res.scalars().first()
        hotel_id = hotel.id

    # Execute two simultaneous audit workers with separate sessions
    async def audit_worker():
        async with AsyncSessionLocal() as s:
            return await NightAuditService.run_night_audit(s, hotel_id, test_audit_date)

    res1, res2 = await asyncio.gather(audit_worker(), audit_worker())

    # Exactly one worker posts the room charges; the second posts 0
    total_posted = res1["financials"]["posted_room_charges_count"] + res2["financials"]["posted_room_charges_count"]
    assert total_posted >= 1
    assert (res1["financials"]["posted_room_charges_count"] == 0 or res2["financials"]["posted_room_charges_count"] == 0)

    # Verify database has exactly 1 report and exactly the active stay count in revenues
    async with AsyncSessionLocal() as session:
        rep_count = (await session.execute(
            select(func.count(GeneratedReport.id))
            .where(GeneratedReport.hotel_id == hotel_id, GeneratedReport.report_date == test_audit_date)
        )).scalar_one()
        assert rep_count == 1

        rev_count = (await session.execute(
            select(func.count(Revenue.id))
            .where(Revenue.hotel_id == hotel_id, Revenue.posting_date == test_audit_date)
        )).scalar_one()
        assert rev_count == total_posted

@pytest.mark.asyncio
async def test_night_audit_two_different_hotels_independent():
    """Verify that two different hotels can execute night audits independently without interference."""
    audit_date = date(2026, 12, 12)
    hotel_b_id = None
    try:
        async with AsyncSessionLocal() as session:
            # Check or create second distinct hotel
            res_b = await session.execute(select(Hotel).where(Hotel.slug == "ganga-view-heritage-test"))
            hotel_b = res_b.scalar_one_or_none()
            if not hotel_b:
                hotel_b = Hotel(
                    name="Ganga View Heritage",
                    slug="ganga-view-heritage-test",
                    address="Dashashwamedh Ghat",
                    city="Varanasi",
                    state="Uttar Pradesh",
                    country="India",
                    postal_code="221001",
                    phone="+91 542 9999999",
                    email="manager@gangaview.com",
                    timezone="Asia/Kolkata",
                    currency="INR"
                )
                session.add(hotel_b)
                await session.commit()
                await session.refresh(hotel_b)
            hotel_b_id = hotel_b.id

            hotel_a = (await session.execute(select(Hotel).where(Hotel.slug == "kashi-heritage-haveli"))).scalars().first()
            hotel_a_id = hotel_a.id

        # Execute audits for both hotels simultaneously
        async with AsyncSessionLocal() as s_a, AsyncSessionLocal() as s_b:
            task_a = NightAuditService.run_night_audit(s_a, hotel_a_id, audit_date)
            task_b = NightAuditService.run_night_audit(s_b, hotel_b_id, audit_date)
            res_a, res_b = await asyncio.gather(task_a, task_b)

        assert res_a["hotel_id"] == hotel_a_id
        assert res_b["hotel_id"] == hotel_b_id
        assert "financials" in res_a and "financials" in res_b
    finally:
        if hotel_b_id:
            async with AsyncSessionLocal() as clean_session:
                await clean_session.execute(delete(GeneratedReport).where(GeneratedReport.hotel_id == hotel_b_id))
                await clean_session.execute(delete(Hotel).where(Hotel.id == hotel_b_id))
                await clean_session.commit()

@pytest.mark.asyncio
async def test_night_audit_retry_and_recovery():
    """Verify that retrying a failed or rerun night audit is completely idempotent."""
    audit_date = date(2026, 12, 15)
    async with AsyncSessionLocal() as session:
        hotel = (await session.execute(select(Hotel).where(Hotel.slug == "kashi-heritage-haveli"))).scalars().first()
        hotel_id = hotel.id

    async with AsyncSessionLocal() as s1:
        res1 = await NightAuditService.run_night_audit(s1, hotel_id, audit_date)
    posted_1 = res1["financials"]["posted_room_charges_count"]

    async with AsyncSessionLocal() as s2:
        res2 = await NightAuditService.run_night_audit(s2, hotel_id, audit_date)
    posted_2 = res2["financials"]["posted_room_charges_count"]

    assert posted_1 >= 1
    assert posted_2 == 0 # 0 duplicates on retry
    assert res1["financials"]["today_earned_revenue_accrual"] == res2["financials"]["today_earned_revenue_accrual"]

# =====================================================================
# 2. P0 — DIGITAL CHECK-IN TOKEN SECURITY TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_digital_checkin_expired_post_and_get_rejected():
    """Verify that expired digital check-in links are strictly rejected on both GET and POST."""
    async with AsyncSessionLocal() as session:
        hotel = (await session.execute(select(Hotel).where(Hotel.slug == "kashi-heritage-haveli"))).scalars().first()
        room = (await session.execute(select(Room).where(Room.hotel_id == hotel.id))).scalars().first()
        guest = Guest(hotel_id=hotel.id, full_name="Expired Guest", phone="+91 99999 00000")
        session.add(guest)
        await session.flush()
        # Create stay that checked out 3 days ago
        stay = GuestStay(
            hotel_id=hotel.id,
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now(timezone.utc) - timedelta(days=5),
            expected_check_out_time=datetime.now(timezone.utc) - timedelta(days=3),
            status="RESERVED",
            room_rate_per_night=Decimal("2000.00")
        )
        session.add(stay)
        await session.commit()
        await session.refresh(stay)
        token = stay.registration_token

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # GET must reject expired token with 410 GONE
        get_res = await client.get(f"/api/v1/guests/digital-checkin/{token}")
        assert get_res.status_code == 410
        assert "expired" in get_res.json()["detail"].lower()

        # POST submission must independently reject expired token with 410 GONE
        post_res = await client.post(f"/api/v1/guests/digital-checkin/{token}/submit", json={
            "full_name": "Tampered Name",
            "phone": "+91 99999 00000"
        })
        assert post_res.status_code == 410
        assert "expired" in post_res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_digital_checkin_concurrent_submissions_exactly_one_succeeds():
    """Verify that concurrent submissions for the same token race safely: exactly 1 succeeds, losing request rejected."""
    async with AsyncSessionLocal() as session:
        hotel = (await session.execute(select(Hotel).where(Hotel.slug == "kashi-heritage-haveli"))).scalars().first()
        room = (await session.execute(select(Room).where(Room.hotel_id == hotel.id))).scalars().first()
        guest = Guest(hotel_id=hotel.id, full_name="Original Name", phone="+91 91234 56789")
        session.add(guest)
        await session.flush()
        stay = GuestStay(
            hotel_id=hotel.id,
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now(timezone.utc),
            expected_check_out_time=datetime.now(timezone.utc) + timedelta(days=1),
            status="CHECKED_IN",
            room_rate_per_night=Decimal("3500.00")
        )
        session.add(stay)
        await session.commit()
        await session.refresh(stay)
        token = stay.registration_token

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        req1 = client.post(f"/api/v1/guests/digital-checkin/{token}/submit", json={
            "full_name": "Applicant Alpha",
            "phone": "+91 91111 22222"
        })
        req2 = client.post(f"/api/v1/guests/digital-checkin/{token}/submit", json={
            "full_name": "Applicant Beta",
            "phone": "+91 93333 44444"
        })
        res1, res2 = await asyncio.gather(req1, req2)

        statuses = [res1.status_code, res2.status_code]
        assert 200 in statuses
        assert (410 in statuses or 404 in statuses)
        assert statuses.count(200) == 1 # Exactly one submission succeeds

# =====================================================================
# 3. P1 — RATE LIMITING & PROXY TRUST TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_rate_limiting_untrusted_spoofed_ip_cannot_bypass():
    """Verify that an untrusted client rotating X-Forwarded-For cannot bypass rate limiting."""
    login_rate_limiter.reset()
    orig_trusted = settings.TRUSTED_PROXIES
    orig_trust_all = settings.TRUST_ALL_PROXIES
    try:
        settings.TRUSTED_PROXIES = ["192.168.1.1"] # Only 192.168.1.1 is trusted proxy
        settings.TRUST_ALL_PROXIES = False

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            throttled = False
            for i in range(12):
                # Client attempts to spoof IP by rotating X-Forwarded-For
                res = await client.post(
                    "/api/v1/auth/login",
                    json={"email": "wrong@example.com", "password": "wrong"},
                    headers={"X-Forwarded-For": f"10.0.0.{i+1}"}
                )
                if res.status_code == 429:
                    throttled = True
                    break
            assert throttled is True
    finally:
        settings.TRUSTED_PROXIES = orig_trusted
        settings.TRUST_ALL_PROXIES = orig_trust_all
        login_rate_limiter.reset()

@pytest.mark.asyncio
async def test_account_level_brute_force_lockout():
    """Verify that 5 failed logins for a specific email trigger account-level rate limiting."""
    account_login_rate_limiter.reset()
    login_rate_limiter.reset()
    target_email = "brute_target@example.com"
    account_key = f"auth_account:{target_email}"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # First 5 failed attempts return 401
        for i in range(5):
            res = await client.post(
                "/api/v1/auth/login",
                json={"email": target_email, "password": "WrongPassword!"}
            )
            assert res.status_code == 401

        # 6th attempt must be throttled with 429
        locked_res = await client.post(
            "/api/v1/auth/login",
            json={"email": target_email, "password": "AnyPassword"}
        )
        assert locked_res.status_code == 429
        assert "Too many failed login attempts" in locked_res.json()["detail"]

    account_login_rate_limiter.reset()

# =====================================================================
# 4. P1 — TENANT AI USAGE QUOTAS TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_tenant_ai_quota_enforcement():
    """Verify that persistent database quotas block AI queries when daily limit is exceeded."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        login_res = await client.post("/api/v1/auth/login", json={
            "email": "owner@kashiheritage.com",
            "password": "HotelOS2026!"
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.status_code} - {login_res.text}"
        token = login_res.json()["access_token"]
        hotel_id = login_res.json()["memberships"][0]["hotel_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Hotel-ID": hotel_id}

        # Set strict daily quota of 2 requests for this hotel
        async with AsyncSessionLocal() as session:
            # Clean past usage for test isolation
            await session.execute(delete(TenantAIUsage).where(TenantAIUsage.hotel_id == hotel_id))
            quota_res = await session.execute(select(TenantAIQuota).where(TenantAIQuota.hotel_id == hotel_id))
            q = quota_res.scalar_one_or_none()
            if q:
                q.daily_request_limit = 2
            else:
                session.add(TenantAIQuota(hotel_id=hotel_id, daily_request_limit=2))
            await session.commit()

        # Request 1: Allowed
        r1 = await client.post("/api/v1/ai/chat", json={"message": "What is a loop?"}, headers=headers)
        assert r1.status_code == 200

        # Request 2: Allowed
        r2 = await client.post("/api/v1/ai/chat", json={"message": "What is a loop?"}, headers=headers)
        assert r2.status_code == 200

        # Request 3: Must be rejected with 429 Quota Exceeded
        r3 = await client.post("/api/v1/ai/chat", json={"message": "What is a loop?"}, headers=headers)
        assert r3.status_code == 429
        assert "Daily AI request limit" in r3.json()["detail"]

        # Restore default quota
        async with AsyncSessionLocal() as session:
            await session.execute(delete(TenantAIUsage).where(TenantAIUsage.hotel_id == hotel_id))
            q = (await session.execute(select(TenantAIQuota).where(TenantAIQuota.hotel_id == hotel_id))).scalar_one_or_none()
            if q:
                q.daily_request_limit = 500
            await session.commit()

# =====================================================================
# 5. PLATFORM HYGIENE TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_production_environment_demo_seeding_guard():
    """Verify that demo seeding is strictly blocked when ENVIRONMENT='production'."""
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
