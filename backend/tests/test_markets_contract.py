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
    """Overview endpoint returns items when data exists; empty list when none."""
    resp = await client.get(
        "/api/markets/overview",
        params={"sort": "volatile", "limit": 50},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "sort" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_markets_refresh_metadata_returns_items(client, auth_headers):
    """Refresh metadata endpoint returns status items."""
    resp = await client.get("/api/markets/refresh-metadata", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)
