"""Contract tests for movements API routes (DB-free via sync bridge mocks)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.common.deps import get_current_user
from app.main import app
from app.modules.visualisation_calc.movements.schemas import (
    MoversCoverageMeta,
    MoversKpi,
    MoversPage,
    MoversSummary,
    MoversSummaryBucket,
)


@pytest.fixture
def movements_auth_override():
    """Bypass DB-backed auth for route contract tests."""

    async def fake_user():
        user = MagicMock()
        user.is_superuser = False
        return user

    app.dependency_overrides[get_current_user] = fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_movements_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert "/api/markets/movements" in paths
    assert "/api/markets/movements/kpi" in paths
    assert "/api/markets/movements/summary" in paths
    assert "/api/markets/movements/coverage" in paths


@pytest.mark.asyncio
async def test_movements_kpi_route_returns_pydantic_model(
    client,
    movements_auth_override,
) -> None:
    with patch(
        "app.modules.visualisation_calc.api._get_movers_kpi_sync",
        return_value=MoversKpi(count=7),
    ):
        resp = await client.get("/api/markets/movements/kpi")
    assert resp.status_code == 200
    assert resp.json() == {"count": 7}


@pytest.mark.asyncio
async def test_movements_summary_route_returns_avg_abs_change(
    client,
    movements_auth_override,
) -> None:
    with patch(
        "app.modules.visualisation_calc.api._get_movers_summary_sync",
        return_value=MoversSummary(
            up_count=2,
            down_count=1,
            unchanged_count=0,
            biggest_gainer=None,
            biggest_loser=None,
            avg_abs_change=Decimal("8.5000"),
            buckets=[
                MoversSummaryBucket(
                    label="5–10%",
                    min_pct=Decimal("5"),
                    max_pct=Decimal("10"),
                    count=1,
                )
            ],
        ),
    ):
        resp = await client.get("/api/markets/movements/summary")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["avg_abs_change"] == "8.5000"


@pytest.mark.asyncio
async def test_movements_coverage_route_maps_filters(
    client,
    movements_auth_override,
) -> None:
    marketplace_id = uuid4()
    captured: dict = {}

    def fake_sync(filters):
        captured["filters"] = filters
        return MoversCoverageMeta(
            listings_with_change=0,
            listings_total=12,
            data_ready=False,
        )

    with patch(
        "app.modules.visualisation_calc.api._get_movers_coverage_sync",
        side_effect=fake_sync,
    ):
        resp = await client.get(
            "/api/markets/movements/coverage",
            params={
                "country_code": "de",
                "period": "7d",
                "marketplace_id": str(marketplace_id),
            },
        )
    assert resp.status_code == 200
    assert resp.json()["data_ready"] is False
    assert captured["filters"].country_code == "DE"
    assert captured["filters"].period == "7d"
    assert captured["filters"].marketplace_id == marketplace_id


@pytest.mark.asyncio
async def test_movements_feed_route_returns_page(
    client,
    movements_auth_override,
) -> None:
    with patch(
        "app.modules.visualisation_calc.api._get_movers_sync",
        return_value=MoversPage(
            items=[],
            total=0,
            limit=20,
            offset=0,
            has_more=False,
        ),
    ):
        resp = await client.get(
            "/api/markets/movements",
            params={"limit": 10, "offset": 0, "threshold": 5},
        )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
