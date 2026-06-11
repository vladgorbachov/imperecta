"""Markets API contract tests. Ingestion, read endpoints, superuser-only ingest."""

import pytest


@pytest.mark.asyncio
async def test_markets_ingest_forbidden_for_regular_user(client, auth_headers):
    """Regular user cannot trigger market data ingestion."""
    resp = await client.post("/api/markets/ingest", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_markets_ingest_forbidden_unauthenticated(client):
    """Unauthenticated caller cannot trigger market data ingestion."""
    resp = await client.post("/api/markets/ingest")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_markets_ingest_ok_for_superuser(client, superuser_headers):
    """Superuser can trigger manual market data refresh."""
    resp = await client.post("/api/markets/ingest", headers=superuser_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "enqueued"
    assert "task_id" in data


@pytest.mark.asyncio
async def test_markets_forex_returns_stored_data(client, auth_headers):
    """Forex endpoint returns items when data exists; empty list when none."""
    resp = await client.get("/api/markets/forex", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "last_refreshed_at" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_markets_overview_returns_stored_data(client, auth_headers):
    """Overview endpoint returns paginated payload from pool data source."""
    resp = await client.get(
        "/api/markets/overview",
        params={"sort": "volatile", "limit": 50},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        first_item = data["items"][0]
        assert "recent_prices" in first_item
        assert isinstance(first_item["recent_prices"], list)


@pytest.mark.asyncio
async def test_markets_refresh_metadata_returns_items(client, auth_headers):
    """Refresh metadata endpoint returns status items."""
    resp = await client.get("/api/markets/refresh-metadata", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_markets_overview_applies_visibility_flag_by_role(client, auth_headers, superuser_headers, monkeypatch):
    """Overview endpoint propagates public/admin visibility flag to pool service."""
    observed: list[bool] = []

    async def fake_list_products(
        _self,
        *,
        sort: str = "recent",
        search: str | None = None,
        marketplace_id=None,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
        include_blocked_countries: bool = False,
    ):
        _ = sort, search, marketplace_id, category, limit, offset
        observed.append(include_blocked_countries)
        return [], 0

    monkeypatch.setattr(
        "app.modules.product_pool.service.ProductPoolService.list_products",
        fake_list_products,
    )

    regular_resp = await client.get("/api/markets/overview", headers=auth_headers)
    assert regular_resp.status_code == 200
    super_resp = await client.get("/api/markets/overview", headers=superuser_headers)
    assert super_resp.status_code == 200
    assert observed == [False, True]


@pytest.mark.asyncio
async def test_pool_categories_applies_visibility_flag_by_role(client, auth_headers, superuser_headers, monkeypatch):
    """Pool categories endpoint propagates visibility flag by role."""
    observed: list[bool] = []

    async def fake_get_categories(_self, *, include_blocked_countries: bool = False):
        observed.append(include_blocked_countries)
        return []

    monkeypatch.setattr(
        "app.modules.product_pool.service.ProductPoolService.get_categories",
        fake_get_categories,
    )

    regular_resp = await client.get("/api/pool/categories", headers=auth_headers)
    assert regular_resp.status_code == 200
    super_resp = await client.get("/api/pool/categories", headers=superuser_headers)
    assert super_resp.status_code == 200
    assert observed == [False, True]


