"""Markets API contract tests. Ingestion, read endpoints, superuser-only ingest."""

from types import SimpleNamespace
from uuid import uuid4

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
async def test_manual_user_scrape_endpoint_enqueues_task(client, auth_headers):
    """Manual scrape endpoint enqueues scrape task for user-owned competitor product."""
    product_resp = await client.post(
        "/api/products/",
        headers=auth_headers,
        json={
            "name": "Manual Scrape Product",
            "current_price": 999.0,
            "currency": "USD",
        },
    )
    assert product_resp.status_code in (200, 201)
    product_id = product_resp.json()["id"]

    competitor_resp = await client.post(
        "/api/competitors/",
        headers=auth_headers,
        json={
            "name": "Manual Scrape Competitor",
            "marketplace": "integration_market",
            "website_url": "https://example.com",
        },
    )
    assert competitor_resp.status_code in (200, 201)
    competitor_id = competitor_resp.json()["id"]

    cp_resp = await client.post(
        "/api/competitors/products",
        headers=auth_headers,
        json={
            "product_id": product_id,
            "competitor_id": competitor_id,
            "url": "https://example.com/product",
            "scraper_type": "universal",
        },
    )
    assert cp_resp.status_code in (200, 201)
    cp_id = cp_resp.json()["id"]

    trigger_resp = await client.post(
        f"/api/competitors/products/{cp_id}/scrape",
        headers=auth_headers,
    )
    assert trigger_resp.status_code == 200
    payload = trigger_resp.json()
    assert payload["status"] == "enqueued"
    assert payload["competitor_product_id"] == cp_id
    assert payload.get("task_id")


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


@pytest.mark.asyncio
async def test_competitor_marketplaces_hide_ru_by_for_regular_user(client, auth_headers, superuser_headers, monkeypatch):
    """Regular user does not receive RU/BY marketplaces; superuser does."""
    async def fake_list_marketplaces(_self):
        return [
            SimpleNamespace(id=uuid4(), name="UA Market", country_code="UA"),
            SimpleNamespace(id=uuid4(), name="RU Market", country_code="RU"),
            SimpleNamespace(id=uuid4(), name="BY Market", country_code="BY"),
        ]

    monkeypatch.setattr(
        "app.modules.marketplaces.service.MarketplaceService.list_marketplaces",
        fake_list_marketplaces,
    )

    regular_resp = await client.get("/api/competitors/marketplaces", headers=auth_headers)
    assert regular_resp.status_code == 200
    regular_names = {item["name"] for item in regular_resp.json()}
    assert regular_names == {"UA Market"}

    super_resp = await client.get("/api/competitors/marketplaces", headers=superuser_headers)
    assert super_resp.status_code == 200
    super_names = {item["name"] for item in super_resp.json()}
    assert super_names == {"UA Market", "RU Market", "BY Market"}
