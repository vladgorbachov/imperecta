"""Edge-cacheable public reads (app.common.public_cache, 2026-09-19).

Storefront data is served anonymously with public cache headers so a CDN can
hold 5-minute snapshots; authenticated (possibly personalised) responses are
private; ETag/If-None-Match gives free revalidation.
"""

from __future__ import annotations

import pytest

from app.common.public_cache import PRIVATE_CACHE_CONTROL, PUBLIC_CACHE_CONTROL


@pytest.mark.asyncio
async def test_pool_stats_anonymous_is_public_with_etag(client):
    resp = await client.get("/api/pool/stats")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == PUBLIC_CACHE_CONTROL
    etag = resp.headers.get("etag")
    assert etag and etag.startswith('W/"')

    again = await client.get("/api/pool/stats", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.headers["etag"] == etag
    assert again.content == b""


@pytest.mark.asyncio
async def test_pool_stats_authenticated_is_private(client, auth_headers):
    resp = await client.get("/api/pool/stats", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == PRIVATE_CACHE_CONTROL
    assert "etag" not in resp.headers


@pytest.mark.asyncio
async def test_bad_token_on_public_route_degrades_to_anonymous(client):
    resp = await client.get(
        "/api/pool/categories", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert resp.status_code == 200
    # A token was presented, so the response stays out of the shared cache.
    assert resp.headers["cache-control"] == PRIVATE_CACHE_CONTROL


@pytest.mark.asyncio
async def test_public_read_routes_need_no_login(client):
    for path in (
        "/api/pool/products?limit=1&skip_total=true",
        "/api/pool/marketplace-stats",
        "/api/markets/kpi-history?days=2",
        "/api/markets/dashboard-kpi",
    ):
        resp = await client.get(path)
        assert resp.status_code == 200, path
        assert resp.headers["cache-control"] == PUBLIC_CACHE_CONTROL, path


@pytest.mark.asyncio
async def test_csv_export_and_writes_stay_authenticated(client):
    assert (await client.get("/api/pool/products/export.csv")).status_code == 401
    assert (await client.post("/api/markets/ingest")).status_code == 401
