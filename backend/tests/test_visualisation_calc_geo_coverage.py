"""DB-free tests for geographic coverage assembly and route contract."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.common.deps import get_current_user
from app.main import app
from app.modules.visualisation_calc.coverage.schemas import CoverageBreakdown, CoverageRow
from app.modules.visualisation_calc.coverage.service import (
    build_country_rollup,
    build_marketplace_breakdown,
)
from tests.route_flatten import iter_app_routes

_MP_A = UUID("11111111-1111-4111-8111-111111111111")
_MP_B = UUID("22222222-2222-4222-8222-222222222222")


@pytest.fixture
def geo_coverage_auth_override():
    """Bypass DB-backed auth for route contract tests."""

    async def fake_user():
        user = MagicMock()
        user.is_superuser = False
        return user

    app.dependency_overrides[get_current_user] = fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_build_country_rollup_share_math() -> None:
    payload = build_country_rollup([("LV", "Latvia", 30), ("LT", "Lithuania", 70)])
    assert payload == CoverageBreakdown(
        mode="countries",
        total=100,
        rows=[
            CoverageRow(
                key="LV",
                label="Latvia",
                country_code="LV",
                count=30,
                share_pct=Decimal("30.00"),
            ),
            CoverageRow(
                key="LT",
                label="Lithuania",
                country_code="LT",
                count=70,
                share_pct=Decimal("70.00"),
            ),
        ],
    )


def test_build_country_rollup_empty_honest() -> None:
    payload = build_country_rollup([])
    assert payload.mode == "countries"
    assert payload.rows == []
    assert payload.total == 0


def test_build_marketplace_breakdown_share_math() -> None:
    payload = build_marketplace_breakdown(
        [
            (_MP_A, "Barbora", "barbora.lv", 25),
            (_MP_B, "Store Beta", "store-beta.example", 75),
        ],
    )
    assert payload.mode == "marketplaces"
    assert payload.total == 100
    assert len(payload.rows) == 2
    assert payload.rows[0].marketplace_id == _MP_A
    assert payload.rows[0].marketplace_domain == "barbora.lv"
    assert payload.rows[0].country_code is None
    assert payload.rows[0].share_pct == Decimal("25.00")
    assert payload.rows[1].share_pct == Decimal("75.00")


def test_build_marketplace_breakdown_empty_honest() -> None:
    payload = build_marketplace_breakdown([])
    assert payload.mode == "marketplaces"
    assert payload.rows == []
    assert payload.total == 0


@pytest.mark.integration
def test_geo_coverage_route_registered() -> None:
    paths = {route.path for route in iter_app_routes(app)}
    assert "/api/markets/geo-coverage" in paths


@pytest.mark.asyncio
async def test_geo_coverage_route_country_rollup(client, geo_coverage_auth_override) -> None:
    with patch(
        "app.modules.visualisation_calc.api.read_country_rollup",
        new_callable=AsyncMock,
        return_value=[],
    ) as read_mock:
        resp = await client.get("/api/markets/geo-coverage")
    assert resp.status_code == 200
    assert resp.json() == {
        "mode": "countries",
        "rows": [],
        "total": 0,
        "pool_total": None,
        "pool_avg_price_eur": None,
        "pool_movers_rate_pct": None,
    }
    read_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_geo_coverage_route_marketplace_breakdown(
    client,
    geo_coverage_auth_override,
) -> None:
    with patch(
        "app.modules.visualisation_calc.api.read_marketplace_breakdown",
        new_callable=AsyncMock,
        return_value=[],
    ) as read_mock:
        resp = await client.get("/api/markets/geo-coverage", params={"country_code": "lv"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "marketplaces"
    read_mock.assert_awaited_once()


def test_world_breakdown_benchmarks_against_grand_pool() -> None:
    from decimal import Decimal
    from uuid import uuid4

    from app.modules.visualisation_calc.coverage.service import (
        build_world_marketplace_breakdown,
    )

    mp = uuid4()
    rows = [(mp, "Amazon", "amazon.com", 50)]
    world_stats = [(mp, Decimal("20.5"), 5, 50)]
    out = build_world_marketplace_breakdown(
        rows,
        world_stats=world_stats,
        pool_total=200,
        pool_avg_price_eur=Decimal("10.25"),
        pool_movers=20,
    )
    assert out.total == 50
    assert out.pool_total == 200
    row = out.rows[0]
    # Zone C: share vs the GRAND pool, not the ZZ subtotal
    assert row.share_pct == Decimal("25.00")
    # Zone D: rates + pool benchmark, never absolutes
    assert row.movers_rate_pct == Decimal("10.00")
    assert row.avg_price_eur == Decimal("20.50")
    assert out.pool_avg_price_eur == Decimal("10.25")
    assert out.pool_movers_rate_pct == Decimal("10.00")


@pytest.mark.asyncio
async def test_geo_coverage_route_world_mode(client, geo_coverage_auth_override) -> None:
    """ZZ branch wires read_world_marketplace_stats + world builder."""
    from decimal import Decimal

    with (
        patch(
            "app.modules.visualisation_calc.api.read_marketplace_breakdown",
            new_callable=AsyncMock,
            return_value=[(_MP_A, "Amazon", "amazon.com", 50)],
        ),
        patch(
            "app.modules.visualisation_calc.api.read_world_marketplace_stats",
            new_callable=AsyncMock,
            return_value=(
                [(_MP_A, Decimal("20.5"), 5, 50)],
                Decimal("10.25"),
                20,
                200,
            ),
        ) as world_mock,
    ):
        resp = await client.get("/api/markets/geo-coverage?country_code=ZZ")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pool_total"] == 200
    assert body["rows"][0]["share_pct"] == "25.00"
    world_mock.assert_awaited_once()
