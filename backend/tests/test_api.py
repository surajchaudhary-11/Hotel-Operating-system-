import pytest
import pytest_asyncio
import httpx
from app.main import app
from app.core.database import AsyncSessionLocal
from app.services.seed_service import seed_initial_data
from app.core.rate_limit import login_rate_limiter, account_login_rate_limiter

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    login_rate_limiter.reset()
    account_login_rate_limiter.reset()
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session, force=True)


async def get_test_auth_context(
    client: httpx.AsyncClient,
    email: str = "owner@kashiheritage.com",
    password: str = "HotelOS2026!"
) -> tuple[str, str, dict]:
    """
    Authenticate a test user against /api/v1/auth/login.
    Safely verifies HTTP 200 and response contract, returning token, hotel_id, and headers.
    """
    login_res = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_res.status_code == 200, (
        f"Authentication failed: HTTP {login_res.status_code} - {login_res.text}"
    )
    data = login_res.json()
    assert "access_token" in data, f"Authentication response missing 'access_token': {data}"
    assert data.get("token_type") == "bearer", f"Expected token_type bearer: {data}"
    assert "memberships" in data and len(data["memberships"]) >= 1, (
        f"User {email} has no active hotel memberships: {data}"
    )
    token = data["access_token"]
    hotel_id = data["memberships"][0]["hotel_id"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Hotel-ID": hotel_id
    }
    return token, hotel_id, headers


@pytest.mark.asyncio
async def test_health_check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert data["service"] == "HotelOS"


@pytest.mark.asyncio
async def test_owner_login():
    """Verify successful login returns valid JWT token and hotel memberships."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/login", json={
            "email": "owner@kashiheritage.com",
            "password": "HotelOS2026!"
        })
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}: {response.text}"
        data = response.json()
        assert "access_token" in data, f"Response missing 'access_token': {data}"
        assert data.get("token_type") == "bearer"
        assert "user" in data
        assert data["user"]["email"] == "owner@kashiheritage.com"
        assert len(data["memberships"]) >= 1
        assert data["memberships"][0]["role"] == "OWNER"


@pytest.mark.asyncio
async def test_login_invalid_password_rejected():
    """Verify that login with incorrect password returns 401 Unauthorized with proper error body."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/login", json={
            "email": "owner@kashiheritage.com",
            "password": "IncorrectPassword2026!"
        })
        assert response.status_code == 401, f"Expected 401 Unauthorized, got {response.status_code}: {response.text}"
        err = response.json()
        assert "detail" in err
        assert err["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_nonexistent_user_rejected():
    """Verify that login with nonexistent user returns 401 Unauthorized with proper error body."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/login", json={
            "email": "nonexistent@kashiheritage.com",
            "password": "HotelOS2026!"
        })
        assert response.status_code == 401, f"Expected 401 Unauthorized, got {response.status_code}: {response.text}"
        err = response.json()
        assert "detail" in err
        assert err["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_tenant_isolation_enforcement():
    # Attempting to fetch rooms without X-Hotel-ID header must return 400
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        token, hotel_id, _ = await get_test_auth_context(client)

        # Call rooms WITHOUT X-Hotel-ID
        res_no_header = await client.get(
            "/api/v1/rooms",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res_no_header.status_code == 400

        # Call rooms WITH valid X-Hotel-ID
        res_with_header = await client.get(
            "/api/v1/rooms",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Hotel-ID": hotel_id
            }
        )
        assert res_with_header.status_code == 200
        rooms = res_with_header.json()
        assert len(rooms) >= 8


@pytest.mark.asyncio
async def test_night_audit_and_report_generation():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        # Trigger night audit
        audit_res = await client.post("/api/v1/reports/trigger-audit", headers=headers)
        assert audit_res.status_code == 200
        report = audit_res.json()["report"]
        assert "occupancy" in report
        assert "financials" in report
        assert report["occupancy"]["total_rooms"] >= 8

        # Fetch PDF
        pdf_res = await client.get("/api/v1/reports/daily/pdf", headers=headers)
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert len(pdf_res.content) > 1000 # Valid generated PDF binary


@pytest.mark.asyncio
async def test_ai_hotel_assistant_occupied_rooms():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        # Ask question about occupancy
        ai_res = await client.post("/api/v1/ai/chat", json={
            "message": "How many rooms are occupied today?"
        }, headers=headers)
        assert ai_res.status_code == 200
        ans = ai_res.json()
        assert "get_occupied_rooms" in ans["tools_executed"]
        assert "occupied" in ans["message"].lower()


@pytest.mark.asyncio
async def test_ai_hotel_assistant_vacant_rooms():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        ai_res = await client.post("/api/v1/ai/chat", json={
            "message": "Which rooms are vacant today?"
        }, headers=headers)
        assert ai_res.status_code == 200
        ans = ai_res.json()
        assert "get_vacant_rooms" in ans["tools_executed"]
        assert "vacant" in ans["message"].lower()


@pytest.mark.asyncio
async def test_ai_hotel_assistant_revenue_summary():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        ai_res = await client.post("/api/v1/ai/chat", json={
            "message": "What was today's revenue and operating contribution?"
        }, headers=headers)
        assert ai_res.status_code == 200
        ans = ai_res.json()
        assert "get_revenue_summary" in ans["tools_executed"]
        assert "operating contribution" in ans["message"].lower()


@pytest.mark.asyncio
async def test_ai_hotel_assistant_hindi_query():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        # Query in Hindi
        ai_res = await client.post("/api/v1/ai/chat", json={
            "message": "आज कितने कमरे खाली हैं?"
        }, headers=headers)
        assert ai_res.status_code == 200
        ans = ai_res.json()
        assert "get_vacant_rooms" in ans["tools_executed"]
        assert "खाली" in ans["message"]


@pytest.mark.asyncio
async def test_ai_hotel_assistant_action_create_housekeeping():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        # Action command to create housekeeping task for Room 102
        ai_res = await client.post("/api/v1/ai/chat", json={
            "message": "Create a cleaning task for Room 102"
        }, headers=headers)
        assert ai_res.status_code == 200
        ans = ai_res.json()
        assert "create_housekeeping_task" in ans["tools_executed"]
        assert "102" in ans["message"]


@pytest.mark.asyncio
async def test_ai_hotel_assistant_conversation_security():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        # Create a conversation
        ai_res = await client.post("/api/v1/ai/chat", json={
            "message": "Hello assistant"
        }, headers=headers)
        conv_id = ai_res.json()["conversation_id"]
        assert conv_id

        # Fetch messages for this valid conversation
        msg_res = await client.get(f"/api/v1/ai/conversations/{conv_id}/messages", headers=headers)
        assert msg_res.status_code == 200
        messages = msg_res.json()
        assert len(messages) >= 2 # User message + Assistant message

        # Accessing with random nonexistent conversation ID must return 404
        fake_res = await client.get("/api/v1/ai/conversations/nonexistent-id/messages", headers=headers)
        assert fake_res.status_code == 404


# =====================================================================
# AI OPERATIONS AGENT: 10 COMPREHENSIVE END-TO-END SCENARIO TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_scenario_1_vacant_rooms_query():
    """Scenario 1: Vacant rooms query retrieves live database status."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        res = await client.post("/api/v1/ai/chat", json={
            "message": "How many rooms are vacant today?"
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "get_vacant_rooms" in data["tools_executed"]
        assert "vacant" in data["message"].lower() or "ready" in data["message"].lower()


@pytest.mark.asyncio
async def test_scenario_2_today_checkins_pii_masked():
    """Scenario 2: Today's check-ins query executes tool and protects guest PII."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        res = await client.post("/api/v1/ai/chat", json={
            "message": "What are today's check-ins?"
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "get_today_checkins" in data["tools_executed"]
        # Ensure full 10-digit phone number is never exposed unmasked
        assert "+91 98765 43210" not in data["message"]


@pytest.mark.asyncio
async def test_scenario_3_rooms_needing_cleaning():
    """Scenario 3: Rooms needing cleaning query executes housekeeping tool."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        res = await client.post("/api/v1/ai/chat", json={
            "message": "Which rooms need cleaning?"
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "get_rooms_needing_cleaning" in data["tools_executed"]


@pytest.mark.asyncio
async def test_scenario_4_low_stock_inventory():
    """Scenario 4: Low-stock inventory query executes stock deficit tool."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        res = await client.post("/api/v1/ai/chat", json={
            "message": "Which inventory items are running low?"
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "get_low_stock_items" in data["tools_executed"]


@pytest.mark.asyncio
async def test_scenario_5_yesterday_revenue_usali():
    """Scenario 5: Yesterday's revenue obeys USALI 11th Edition rules."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        res = await client.post("/api/v1/ai/chat", json={
            "message": "What was yesterday's room revenue?"
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "get_revenue_summary" in data["tools_executed"]
        assert "operating contribution" in data["message"].lower()


@pytest.mark.asyncio
async def test_scenario_6_action_proposal_confirmation_and_duplicate_prevention():
    """Scenario 6: Consequential actions return proposals, require confirmation, and block duplicates."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        # Step 1: Request consequential action (Propose creation)
        prop_res = await client.post("/api/v1/ai/chat", json={
            "message": "Create a housekeeping task for Room 102"
        }, headers=headers)
        assert prop_res.status_code == 200
        prop_data = prop_res.json()
        proposal = prop_data.get("action_proposal")
        assert proposal is not None
        assert proposal["action_name"] == "create_housekeeping_task"
        assert proposal["status"] == "pending_confirmation"
        assert proposal["parameters"]["room_number"] == "102"
        action_id = proposal["action_id"]

        # Step 2: Confirm and execute proposal
        conf_res = await client.post("/api/v1/ai/chat", json={
            "message": "Confirm action",
            "confirm_action_id": action_id,
            "action_name": proposal["action_name"],
            "action_parameters": proposal["parameters"],
            "conversation_id": prop_data["conversation_id"]
        }, headers=headers)
        assert conf_res.status_code == 200
        conf_data = conf_res.json()
        assert conf_data["action_executed"] is not None
        assert conf_data["action_executed"]["result"]["success"] is True
        assert conf_data["action_proposal"]["status"] == "executed"

        # Step 3: Attempt duplicate execution with same action_id
        dup_res = await client.post("/api/v1/ai/chat", json={
            "message": "Confirm action",
            "confirm_action_id": action_id,
            "action_name": proposal["action_name"],
            "action_parameters": proposal["parameters"],
            "conversation_id": prop_data["conversation_id"]
        }, headers=headers)
        assert dup_res.status_code == 200
        dup_data = dup_res.json()
        assert "already been executed" in dup_data["message"].lower()


@pytest.mark.asyncio
async def test_scenario_7_unauthorized_role_access():
    """Scenario 7: Unauthorized role is rejected from executing privileged tools."""
    from app.core.dependencies import TenantContext
    from app.services.ai_tools import tool_get_revenue_summary, tool_assign_housekeeping_task

    # Create dummy tenant context for a staff member with HOUSEKEEPER role
    class MockUser:
        id = "mock-housekeeper-id"
        email = "cleaner@hotel.com"

    class MockHotel:
        name = "Kashi Heritage Haveli"

    ctx_housekeeper = TenantContext(
        hotel_id="hotel-test-id",
        role="HOUSEKEEPER",
        hotel=MockHotel(),
        user=MockUser()
    )

    async with AsyncSessionLocal() as session:
        # Financial query must reject HOUSEKEEPER
        fin_res = await tool_get_revenue_summary(db=session, ctx=ctx_housekeeper)
        assert fin_res["authorized"] is False

        # Task reassignment must reject HOUSEKEEPER
        assign_res = await tool_assign_housekeeping_task(
            db=session, ctx=ctx_housekeeper, task_id="task-1", staff_email_or_name="test"
        )
        assert assign_res["success"] is False
        assert "not authorized" in assign_res["message"].lower()


@pytest.mark.asyncio
async def test_scenario_8_unauthenticated_request_rejected():
    """Scenario 8: Unauthenticated request is rejected with 401."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/v1/ai/chat", json={
            "message": "How many rooms are vacant?"
        })
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_scenario_9_cross_hotel_isolation():
    """Scenario 9: Cross-hotel isolation prevents accessing other hotels' data."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        token, _, _ = await get_test_auth_context(client)

        # Call with nonexistent or alien hotel ID
        res = await client.post(
            "/api/v1/ai/chat",
            json={"message": "Show me room status"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Hotel-ID": "00000000-0000-0000-0000-000000000000"
            }
        )
        # Should be 403 or 400 because user has no membership in this foreign hotel
        assert res.status_code in [400, 403]


@pytest.mark.asyncio
async def test_scenario_10_missing_api_key_handling():
    """Scenario 10: Missing external LLM credentials returns clean configuration notice without crashing."""
    from app.core.config import settings

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        # Save original settings
        orig_provider = settings.AI_PROVIDER
        orig_key = settings.OPENAI_API_KEY

        try:
            # Force external provider with no key
            settings.AI_PROVIDER = "openai"
            settings.OPENAI_API_KEY = ""

            res = await client.post("/api/v1/ai/chat", json={
                "message": "How many rooms are vacant?"
            }, headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert "OPENAI_API_KEY" in data["message"]
            assert "Configuration Notice" in data["message"]
        finally:
            settings.AI_PROVIDER = orig_provider
            settings.OPENAI_API_KEY = orig_key


@pytest.mark.asyncio
async def test_general_knowledge_loop_query():
    """Scenario 11: General knowledge query (What is a loop?) answered directly without operational tools."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        res = await client.post("/api/v1/ai/chat", json={
            "message": "What is a loop?"
        }, headers=headers)

        assert res.status_code == 200
        data = res.json()
        assert data["tools_executed"] == []
        assert "loop" in data["message"].lower()
        assert len(data["message"]) > 40


@pytest.mark.asyncio
async def test_general_knowledge_functions_query():
    """Scenario 12: General knowledge query (Explain Python functions) returns code examples without querying DB."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        res = await client.post("/api/v1/ai/chat", json={
            "message": "Explain Python functions."
        }, headers=headers)

        assert res.status_code == 200
        data = res.json()
        assert data["tools_executed"] == []
        assert "def " in data["message"] or "function" in data["message"].lower()


@pytest.mark.asyncio
async def test_general_knowledge_hotel_analogy():
    """Scenario 13: Technical concept explained using hotel analogy without running DB tools."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        _, _, headers = await get_test_auth_context(client)

        res = await client.post("/api/v1/ai/chat", json={
            "message": "Explain loops using a hotel example."
        }, headers=headers)

        assert res.status_code == 200
        data = res.json()
        assert data["tools_executed"] == []
        assert "room" in data["message"].lower() or "hotel" in data["message"].lower()
        assert "loop" in data["message"].lower()


def test_classify_intent():
    """Scenario 14: Intent classifier correctly categorizes inputs."""
    from app.services.ai_service import classify_intent

    assert classify_intent("What is a loop?") == "GENERAL_KNOWLEDGE"
    assert classify_intent("Explain Python functions") == "GENERAL_KNOWLEDGE"
    assert classify_intent("How does JavaScript async await work?") == "GENERAL_KNOWLEDGE"
    assert classify_intent("Explain loops using a hotel example") == "HOTEL_ANALOGY"
    assert classify_intent("How many rooms are vacant?") == "HOTEL_DATA"
    assert classify_intent("आज कितने कमरे खाली हैं?") == "HOTEL_DATA"
    assert classify_intent("Create a housekeeping task for Room 101") == "HOTEL_ACTION"
    assert classify_intent("What are today's check-ins?") == "HOTEL_DATA"
    assert classify_intent("status") == "AMBIGUOUS"
    assert classify_intent("hi") == "GENERAL_KNOWLEDGE"
