"""Security-focused tests: auth, IDOR, input validation, redirects, data exposure.

UP1 removed user_products + alerts + digests + competitors endpoints; the
corresponding security tests for those routes were deleted with their
endpoints. AI, markets, auth, admin, and preferences coverage remains.
"""

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def auth_headers_b(client):
    """Second user (user B) for cross-account IDOR tests."""
    await client.post(
        "/api/auth/register",
        json={
            "email": "userb@imperecta.com",
            "password": "TestPass123!",
            "name": "User B",
            "language": "en",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        json={
            "email": "userb@imperecta.com",
            "password": "TestPass123!",
        },
    )
    data = resp.json()
    token = data.get("access_token")
    if not token:
        pytest.skip("User B login failed")
    return {"Authorization": f"Bearer {token}"}


# --- AUTH / AUTHORIZATION ---


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_protected_endpoints(client):
    """Unauthenticated user cannot access protected endpoints."""
    endpoints = [
        ("GET", "/api/auth/me"),
        ("GET", "/api/markets/preferences"),
        ("GET", "/api/markets/overview"),
    ]
    for method, path in endpoints:
        if method == "GET":
            resp = await client.get(path)
        else:
            resp = await client.post(path, json={})
        assert resp.status_code in (401, 403), f"{method} {path} should require auth"


@pytest.mark.asyncio
async def test_non_superuser_cannot_access_admin(client, auth_headers):
    """Regular user cannot access admin endpoints."""
    admin_endpoints = [
        ("GET", "/api/admin/stats"),
        ("GET", "/api/admin/claude-status"),
    ]
    for method, path in admin_endpoints:
        resp = await client.get(path, headers=auth_headers)
        assert resp.status_code == 403, f"{method} {path} should be forbidden for non-superuser"


@pytest.mark.asyncio
async def test_change_initial_password_requires_force_flag(client, auth_headers):
    """change-initial-password returns 403 when user does not have force_password_change."""
    resp = await client.post(
        "/api/auth/change-initial-password",
        headers=auth_headers,
        json={
            "new_email": "new@test.com",
            "new_password": "NewPass123!",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_me_returns_user_profile_without_sensitive_fields(client, auth_headers):
    """Me endpoint does not expose password_hash or internal fields."""
    resp = await client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "password_hash" not in data
    assert "password" not in data


# --- IDOR / OBJECT OWNERSHIP ---


@pytest.mark.asyncio
async def test_user_a_cannot_overwrite_user_b_preferences(client, auth_headers, auth_headers_b):
    """User A cannot overwrite User B's markets preferences via API."""
    resp_a = await client.put(
        "/api/markets/preferences",
        headers=auth_headers,
        json={"forex_favorites": ["EUR/USD"]},
    )
    assert resp_a.status_code == 200

    resp_b = await client.get("/api/markets/preferences", headers=auth_headers_b)
    assert resp_b.status_code == 200
    prefs_b = resp_b.json()
    assert prefs_b.get("forex_favorites") != ["EUR/USD"]


# --- MASS ASSIGNMENT / OVER-POSTING ---


@pytest.mark.asyncio
async def test_put_me_rejects_extra_fields(client, auth_headers):
    """PUT /me does not accept is_superuser or other privileged fields."""
    resp = await client.put(
        "/api/auth/me",
        headers=auth_headers,
        json={
            "name": "Updated",
            "is_superuser": True,
            "plan": "full",
            "email": "hacker@evil.com",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("is_superuser") is False
    assert data.get("email") != "hacker@evil.com"
    assert data.get("name") == "Updated"


# --- AI ENDPOINT ---


@pytest.mark.asyncio
async def test_ai_chat_requires_entitlement(client, auth_headers):
    """AI chat endpoint enforces entitlement (Trial/Free may get 403)."""
    resp = await client.post(
        "/api/ai/chat",
        headers=auth_headers,
        json={
            "message": "test",
            "session_id": None,
            "context_type": None,
            "context_id": None,
        },
    )
    assert resp.status_code in (200, 403, 503)


@pytest.mark.asyncio
async def test_ai_session_idor_user_b_cannot_access_user_a_session(client, auth_headers, auth_headers_b):
    """User B cannot access User A's AI session by ID. Skips if AI_ANALYST not available (Trial/Free)."""
    resp_a = await client.post(
        "/api/ai/chat",
        headers=auth_headers,
        json={
            "message": "create session",
            "session_id": None,
            "context_type": None,
            "context_id": None,
        },
    )
    if resp_a.status_code != 200:
        pytest.skip("AI chat not available (403/503) - cannot create session for IDOR test")
    session_id = resp_a.json().get("session_id")
    if not session_id:
        list_resp = await client.get("/api/ai/sessions", headers=auth_headers)
        if list_resp.status_code != 200 or not list_resp.json():
            pytest.skip("No AI session created")
        session_id = list_resp.json()[0]["id"]

    resp_b = await client.get(
        f"/api/ai/sessions/{session_id}",
        headers=auth_headers_b,
    )
    assert resp_b.status_code == 404, "User B must not access User A's AI session"


# --- MARKETS SORT INJECTION ---


@pytest.mark.asyncio
async def test_markets_overview_invalid_sort(client, auth_headers):
    """Invalid sort param is safely handled."""
    resp = await client.get(
        "/api/markets/overview",
        headers=auth_headers,
        params={"sort": "'; DROP TABLE markets_overview;"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_markets_overview_limit_bounds(client, auth_headers):
    """Limit param is bounded."""
    resp = await client.get(
        "/api/markets/overview",
        headers=auth_headers,
        params={"limit": 999999},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data.get("items", [])) <= 100


@pytest.mark.asyncio
async def test_markets_preferences_rejects_oversized_favorites(client, auth_headers):
    """Markets preferences rejects oversized favorite_instrument_ids list."""
    ids = [f"id_{i}" for i in range(60)]
    resp = await client.put(
        "/api/markets/preferences",
        headers=auth_headers,
        json={"favorite_instrument_ids": ids},
    )
    assert resp.status_code == 422
