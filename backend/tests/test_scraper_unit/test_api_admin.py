"""Admin scraper API: TestClient + dependency overrides (no DB for enqueue routes)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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
    assert admin_client.post("/api/admin/pool/trigger-scrape").status_code == 404
    assert admin_client.post("/api/admin/discovery/trigger-all").status_code == 404
    assert (
        admin_client.post("/api/admin/discovery/trigger/00000000-0000-0000-0000-000000000001").status_code
        == 404
    )
    assert admin_client.post("/api/admin/db-diagnostics").status_code == 404
    assert admin_client.get("/api/admin/scrape-diagnostics").status_code == 404
    assert (
        admin_client.post("/api/admin/scrape/test-single/00000000-0000-0000-0000-000000000001").status_code
        == 404
    )


def test_removed_scraper_admin_endpoints_not_in_openapi_schema(admin_client):
    schema = admin_client.app.openapi()
    paths = schema.get("paths", {})
    assert "/api/admin/trigger-scrape" not in paths
    assert "/api/admin/scrape-activity" not in paths
    assert "/api/admin/error-distribution" not in paths
    assert "/api/pool/products/bulk" not in paths
    assert "/api/admin/products/clear-test-data" not in paths
    assert "/api/admin/marketplaces/deduplicate" not in paths
    assert "/api/auth/avatar" not in paths
    assert "/api/admin/pool/trigger-scrape" not in paths
    assert "/api/admin/discovery/trigger-all" not in paths
    assert "/api/admin/discovery/trigger/{marketplace_id}" not in paths
    assert "/api/admin/db-diagnostics" not in paths
    assert "/api/admin/scrape-diagnostics" not in paths
    assert "/api/admin/scrape/test-single/{listing_id}" not in paths


