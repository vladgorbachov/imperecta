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
