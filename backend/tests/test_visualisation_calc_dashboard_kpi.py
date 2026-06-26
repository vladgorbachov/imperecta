"""DB-free tests for dashboard KPI assembly and route contract."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.common.deps import get_current_user
from app.main import app
from app.modules.visualisation_calc.kpi.schemas import DashboardKpi
from app.modules.visualisation_calc.kpi.service import build_dashboard_kpi


@pytest.fixture
def dashboard_kpi_auth_override():
    """Bypass DB-backed auth for route contract tests."""

    async def fake_user():
        user = MagicMock()
        user.is_superuser = False
        return user

    app.dependency_overrides[get_current_user] = fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_build_dashboard_kpi_packs_values() -> None:
    ts = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
    payload = build_dashboard_kpi(42, ts)
    assert payload == DashboardKpi(updated_24h=42, last_update=ts)


def test_build_dashboard_kpi_preserves_null_last_update() -> None:
    payload = build_dashboard_kpi(0, None)
    assert payload.updated_24h == 0
    assert payload.last_update is None


def test_dashboard_kpi_route_registered() -> None:
    paths = {route.path for route in app.routes}
    assert "/api/markets/dashboard-kpi" in paths


@pytest.mark.asyncio
async def test_dashboard_kpi_route_returns_model(
    client,
    dashboard_kpi_auth_override,
) -> None:
    ts = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
    with patch(
        "app.modules.visualisation_calc.api.read_dashboard_kpi",
        new_callable=AsyncMock,
        return_value=(0, None),
    ) as read_mock:
        resp = await client.get("/api/markets/dashboard-kpi")
    assert resp.status_code == 200
    assert resp.json() == {"updated_24h": 0, "last_update": None}
    read_mock.assert_awaited_once()

    with patch(
        "app.modules.visualisation_calc.api.read_dashboard_kpi",
        new_callable=AsyncMock,
        return_value=(3, ts),
    ):
        resp = await client.get(
            "/api/markets/dashboard-kpi",
            params={"country_code": "de"},
        )
    assert resp.status_code == 200
    assert resp.json()["updated_24h"] == 3
    assert resp.json()["last_update"] is not None
