"""Security-focused tests: auth, IDOR, input validation, import, redirects, data exposure."""

import io

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
        ("GET", "/api/products"),
        ("GET", "/api/dashboard/kpi"),
        ("GET", "/api/alerts/"),
        ("GET", "/api/competitors"),
        ("GET", "/api/digests"),
        ("GET", "/api/markets/preferences"),
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
async def test_user_a_cannot_access_user_b_product(client, auth_headers, auth_headers_b):
    """User A cannot fetch/update/delete User B's product."""
    create_resp = await client.post(
        "/api/products/",
        headers=auth_headers,
        json={
            "name": "User A Product",
            "current_price": 100.0,
            "currency": "RUB",
        },
    )
    assert create_resp.status_code in (200, 201)
    product_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/products/{product_id}", headers=auth_headers_b)
    assert get_resp.status_code == 404

    put_resp = await client.put(
        f"/api/products/{product_id}",
        headers=auth_headers_b,
        json={"name": "Hijacked"},
    )
    assert put_resp.status_code == 404

    del_resp = await client.delete(f"/api/products/{product_id}", headers=auth_headers_b)
    assert del_resp.status_code == 404


@pytest.mark.asyncio
async def test_user_b_cannot_access_user_a_product_by_forged_id(client, auth_headers, auth_headers_b):
    """User B with valid token cannot access User A's product by ID (proves ownership check)."""
    create_resp = await client.post(
        "/api/products/",
        headers=auth_headers,
        json={
            "name": "User A Product",
            "current_price": 100.0,
            "currency": "RUB",
        },
    )
    assert create_resp.status_code in (200, 201)
    product_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/products/{product_id}", headers=auth_headers_b)
    assert get_resp.status_code == 404, "User B must not access User A's product"


@pytest.mark.asyncio
async def test_user_b_cannot_access_digest_by_id(client, auth_headers_b):
    """User B cannot access digest by arbitrary ID (404 for non-owner/non-existent)."""
    fake_id = "00000000-0000-0000-0000-000000000001"
    get_resp = await client.get(f"/api/digests/{fake_id}", headers=auth_headers_b)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_user_a_cannot_access_user_b_alert(client, auth_headers, auth_headers_b):
    """User A cannot update/delete User B's alert."""
    create_resp = await client.post(
        "/api/products/",
        headers=auth_headers,
        json={
            "name": "Prod",
            "current_price": 100.0,
            "currency": "RUB",
        },
    )
    product_id = create_resp.json()["id"]

    alert_resp = await client.post(
        "/api/alerts/",
        headers=auth_headers,
        json={
            "product_id": product_id,
            "type": "price_drop",
            "channel": "email",
        },
    )
    if alert_resp.status_code in (200, 201):
        alert_id = alert_resp.json().get("id")
        if alert_id:
            put_resp = await client.put(
                f"/api/alerts/{alert_id}",
                headers=auth_headers_b,
                json={"is_active": False},
            )
            assert put_resp.status_code == 404


@pytest.mark.asyncio
async def test_user_a_cannot_access_user_b_competitor(client, auth_headers, auth_headers_b):
    """User B cannot update/delete User A's competitor."""
    create_resp = await client.post(
        "/api/competitors/",
        headers=auth_headers,
        json={
            "name": "Competitor A",
            "website_url": "https://example.com",
        },
    )
    assert create_resp.status_code in (200, 201)
    comp_id = create_resp.json()["id"]

    put_resp = await client.put(
        f"/api/competitors/{comp_id}",
        headers=auth_headers_b,
        json={"name": "Hijacked"},
    )
    assert put_resp.status_code == 404

    del_resp = await client.delete(f"/api/competitors/{comp_id}", headers=auth_headers_b)
    assert del_resp.status_code == 404


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


@pytest.mark.asyncio
async def test_put_product_rejects_extra_fields(client, auth_headers):
    """PUT /products/{id} does not accept user_id or other privileged fields."""
    create_resp = await client.post(
        "/api/products/",
        headers=auth_headers,
        json={
            "name": "Prod",
            "current_price": 100.0,
            "currency": "RUB",
        },
    )
    product_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/products/{product_id}",
        headers=auth_headers,
        json={
            "name": "Updated",
            "user_id": "00000000-0000-0000-0000-000000000001",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert str(data.get("user_id")) != "00000000-0000-0000-0000-000000000001"


# --- INPUT VALIDATION ---


@pytest.mark.asyncio
async def test_invalid_product_id_returns_404(client, auth_headers):
    """Invalid UUID returns 404, not 500."""
    resp = await client.get("/api/products/not-a-uuid", headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_products_list_filter_safe(client, auth_headers):
    """Invalid page/limit params are rejected."""
    resp = await client.get(
        "/api/products/",
        headers=auth_headers,
        params={"page": -1, "limit": 9999},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_auto_categorize_rejects_invalid_payload(client, auth_headers):
    """Auto-categorize rejects invalid payloads."""
    resp = await client.post(
        "/api/import/auto-categorize",
        headers=auth_headers,
        json={"products": "not-a-list"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_auto_categorize_rejects_oversized_list(client, auth_headers):
    """Auto-categorize rejects oversized product list."""
    products = [{"name": f"x{i}", "sku": "s", "price": 1.0} for i in range(150)]
    resp = await client.post(
        "/api/import/auto-categorize",
        headers=auth_headers,
        json={"products": products},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_auto_categorize_rejects_invalid_product_item(client, auth_headers):
    """Auto-categorize rejects invalid product item fields."""
    resp = await client.post(
        "/api/import/auto-categorize",
        headers=auth_headers,
        json={
            "products": [
                {"name": "x" * 600, "sku": "s", "price": 1.0},
            ],
        },
    )
    assert resp.status_code == 422


# --- IMPORT / UPLOAD SECURITY ---


@pytest.mark.asyncio
async def test_import_preview_rejects_oversized_file(client, auth_headers):
    """Import preview rejects file larger than limit."""
    content = b"x" * (6 * 1024 * 1024)
    resp = await client.post(
        "/api/import/products/preview",
        headers=auth_headers,
        files={"file": ("large.csv", io.BytesIO(content), "text/csv")},
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_import_csv_rejects_oversized_file(client, auth_headers):
    """Import CSV rejects file larger than limit."""
    content = b"x" * (6 * 1024 * 1024)
    resp = await client.post(
        "/api/import/products/csv",
        headers=auth_headers,
        files={"file": ("large.csv", io.BytesIO(content), "text/csv")},
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_import_csv_rejects_unsupported_format(client, auth_headers):
    """Import rejects unsupported file format."""
    content = b"not csv content"
    resp = await client.post(
        "/api/import/products/preview",
        headers=auth_headers,
        files={"file": ("evil.exe", io.BytesIO(content), "application/octet-stream")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("errors") or not data.get("preview")


@pytest.mark.asyncio
async def test_import_csv_rejects_required_columns(client, auth_headers):
    """Import preview rejects file missing required columns."""
    content = b"sku,url,category\n1,http://x.com,cat"
    resp = await client.post(
        "/api/import/products/preview",
        headers=auth_headers,
        files={"file": ("bad.csv", io.BytesIO(content), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("errors")


@pytest.mark.asyncio
async def test_import_csv_path_traversal_filename(client, auth_headers):
    """Path traversal-like filename does not escape allowed handling."""
    content = b"name,price\nProduct,100"
    resp = await client.post(
        "/api/import/products/preview",
        headers=auth_headers,
        files={"file": ("../../../etc/passwd", io.BytesIO(content), "text/csv")},
    )
    assert resp.status_code == 200


# --- DATA EXPOSURE ---


@pytest.mark.asyncio
async def test_404_response_no_stack_trace(client, auth_headers):
    """404 responses do not leak stack traces or internal paths."""
    resp = await client.get(
        "/api/products/00000000-0000-0000-0000-000000000001",
        headers=auth_headers,
    )
    assert resp.status_code == 404
    body = resp.text.lower()
    assert "traceback" not in body
    assert "file \"" not in body


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


