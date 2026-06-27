"""Admin alert endpoints — contract tests (DB-free via mocked reads)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.common.deps import get_current_user
from app.database import get_db
from app.main import app


@pytest.fixture
def alerts_db_client():
    async def fake_db():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = fake_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _override_user(*, is_superuser: bool):
    async def fake_user():
        user = MagicMock()
        user.is_superuser = is_superuser
        return user

    app.dependency_overrides[get_current_user] = fake_user


def test_service_alerts_endpoint_in_openapi(alerts_db_client):
    _override_user(is_superuser=True)
    schema = alerts_db_client.app.openapi()
    path = schema["paths"]["/api/admin/service_alerts"]["get"]
    assert "admin-alerts" in path["tags"]
    params = {p["name"] for p in path.get("parameters", [])}
    assert {"module", "submodule", "severity", "resolved", "limit", "offset"} <= params


def test_analytic_alerts_endpoint_in_openapi(alerts_db_client):
    _override_user(is_superuser=True)
    schema = alerts_db_client.app.openapi()
    path = schema["paths"]["/api/admin/analytic_alerts"]["get"]
    params = {p["name"] for p in path.get("parameters", [])}
    assert {"alert_type", "severity", "user_id", "limit", "offset"} <= params


def test_service_alerts_forbidden_for_regular_user(alerts_db_client):
    _override_user(is_superuser=False)
    resp = alerts_db_client.get("/api/admin/service_alerts")
    assert resp.status_code == 403


def test_analytic_alerts_forbidden_for_regular_user(alerts_db_client):
    _override_user(is_superuser=False)
    resp = alerts_db_client.get("/api/admin/analytic_alerts")
    assert resp.status_code == 403


@patch("app.modules.admin.api_alerts.list_service_alerts", new_callable=AsyncMock)
def test_service_alerts_superuser_filterable_shape(mock_list, alerts_db_client):
    _override_user(is_superuser=True)
    mock_list.return_value = {
        "items": [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "alert_class": "service",
                "module": "discovery",
                "submodule": "budget_governor",
                "severity": "warning",
                "anomaly_type": "detector_divergence",
                "message": "test",
                "context": None,
                "triggered_at": "2026-06-17T00:00:00+00:00",
                "resolved_at": None,
            }
        ],
        "total": 1,
        "limit": 50,
        "offset": 0,
    }

    resp = alerts_db_client.get(
        "/api/admin/service_alerts",
        params={
            "module": "discovery",
            "submodule": "budget_governor",
            "severity": "warning",
            "resolved": "open",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["alert_class"] == "service"
    mock_list.assert_awaited_once()
    call_kwargs = mock_list.await_args.kwargs
    assert call_kwargs["module"] == "discovery"
    assert call_kwargs["submodule"] == "budget_governor"
    assert call_kwargs["severity"] == "warning"
    assert call_kwargs["resolved"] == "open"


@patch("app.modules.admin.api_alerts.list_analytic_alerts", new_callable=AsyncMock)
def test_analytic_alerts_superuser_filterable_shape(mock_list, alerts_db_client):
    _override_user(is_superuser=True)
    mock_list.return_value = {
        "items": [
            {
                "id": 1,
                "alert_class": "analytic",
                "alert_id": "00000000-0000-0000-0000-000000000002",
                "alert_type": "price_drop",
                "user_id": "00000000-0000-0000-0000-000000000003",
                "listing_id": None,
                "severity": "medium",
                "message": "Price dropped",
                "old_value": 10.0,
                "new_value": 8.0,
                "change_pct": -20.0,
                "triggered_at": "2026-06-17T00:00:00+00:00",
                "read_at": None,
            }
        ],
        "total": 1,
        "limit": 50,
        "offset": 0,
    }

    resp = alerts_db_client.get(
        "/api/admin/analytic_alerts",
        params={"alert_type": "price_drop", "severity": "medium"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["alert_class"] == "analytic"
    mock_list.assert_awaited_once()
