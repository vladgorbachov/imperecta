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


def test_trigger_scrape_enqueue(admin_client):
    mock_task = MagicMock()
    mock_task.id = "test-task-id"
    with patch("app.modules.scraper.api.scrape_all") as m:
        m.delay.return_value = mock_task
        resp = admin_client.post("/api/admin/trigger-scrape")
    assert resp.status_code == 200
    assert resp.json().get("task_id") == "test-task-id"


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


def test_scrape_activity_and_error_distribution(admin_client):
    assert admin_client.get("/api/admin/scrape-activity").status_code == 200
    assert admin_client.get("/api/admin/error-distribution").status_code == 200


def test_scrape_diagnostics_and_test_single_in_openapi_schema(admin_client):
    schema = admin_client.app.openapi()
    paths = schema.get("paths", {})
    assert "/api/admin/scrape-diagnostics" in paths
    assert "get" in paths["/api/admin/scrape-diagnostics"]
    assert "/api/admin/scrape/test-single/{listing_id}" in paths
    assert "post" in paths["/api/admin/scrape/test-single/{listing_id}"]


