"""Admin scraper API: TestClient + dependency overrides (no DB for enqueue routes)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.common.deps import get_current_superuser
from app.database import get_db
from app.main import app


@pytest.fixture
def admin_client():
    async def fake_db():
        session = AsyncMock()
        yield session

    async def fake_super():
        u = MagicMock()
        u.is_superuser = True
        return u

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_superuser] = fake_super
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_pool_and_discovery_triggers(admin_client):
    mock_task = MagicMock()
    mock_task.id = "q1"
    with (
        patch("app.modules.scraper.api.scrape_all_pool_products") as p1,
        patch("app.modules.scraper.api.discover_all_marketplaces") as p2,
        patch("app.modules.scraper.api.discover_single_marketplace") as p3,
    ):
        p1.delay.return_value = mock_task
        p2.delay.return_value = mock_task
        p3.delay.return_value = mock_task
        mp_id = "00000000-0000-0000-0000-000000000001"
        assert admin_client.post("/api/admin/pool/trigger-scrape").status_code == 200
        assert admin_client.post("/api/admin/discovery/trigger-all").status_code == 200
        assert admin_client.post(f"/api/admin/discovery/trigger/{mp_id}").status_code == 200


def test_removed_legacy_endpoints_not_found(admin_client):
    assert admin_client.post("/api/admin/trigger-scrape").status_code == 404
    assert admin_client.get("/api/admin/scrape-activity").status_code == 404
    assert admin_client.get("/api/admin/error-distribution").status_code == 404
    assert (
        admin_client.request(
            "DELETE",
            "/api/pool/products/bulk",
            json={"product_ids": [1]},
        ).status_code
        == 404
    )
    assert admin_client.delete("/api/admin/products/clear-test-data").status_code == 404
    assert admin_client.post("/api/admin/marketplaces/deduplicate").status_code in (404, 405)
    assert admin_client.delete("/api/auth/avatar").status_code == 404


def test_scrape_diagnostics_and_test_single_in_openapi_schema(admin_client):
    schema = admin_client.app.openapi()
    paths = schema.get("paths", {})
    assert "/api/admin/trigger-scrape" not in paths
    assert "/api/admin/scrape-activity" not in paths
    assert "/api/admin/error-distribution" not in paths
    assert "/api/pool/products/bulk" not in paths
    assert "/api/admin/products/clear-test-data" not in paths
    assert "/api/admin/marketplaces/deduplicate" not in paths
    assert "/api/auth/avatar" not in paths
    assert "/api/admin/scrape-diagnostics" in paths
    assert "get" in paths["/api/admin/scrape-diagnostics"]
    assert "/api/admin/db-diagnostics" in paths
    assert "post" in paths["/api/admin/db-diagnostics"]
    assert "/api/admin/scrape/test-single/{listing_id}" in paths
    assert "post" in paths["/api/admin/scrape/test-single/{listing_id}"]


def test_db_diagnostics_post(admin_client, monkeypatch):
    def fake_collect(_engine):
        return {"alembic_version": "test", "counts": {}, "errors": []}

    monkeypatch.setattr("app.modules.scraper.api.collect_db_diagnostics", fake_collect)
    resp = admin_client.post("/api/admin/db-diagnostics")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("alembic_version") == "test"


