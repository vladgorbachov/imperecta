"""DB-free tests for trend series assembly and route contract."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.common.deps import get_current_user
from app.main import app
from app.modules.visualisation_calc.trend.schemas import TrendPoint, TrendSeries
from app.modules.visualisation_calc.trend.service import build_trend_series


@pytest.fixture
def trend_auth_override():
    """Bypass DB-backed auth for route contract tests."""

    async def fake_user():
        user = MagicMock()
        user.is_superuser = False
        return user

    app.dependency_overrides[get_current_user] = fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_build_trend_series_formats_day_labels() -> None:
    series = build_trend_series(
        [
            (date(2026, 6, 1), Decimal("10.456"), 3),
            (date(2026, 6, 2), Decimal("12"), 2),
        ],
        period="30d",
        bucket="day",
    )
    assert series.points[0].bucket_label == "2026-06-01"
    assert series.points[0].avg_price_eur == Decimal("10.46")
    assert series.data_ready is True
    assert series.currency == "EUR"


def test_build_trend_series_week_and_month_labels() -> None:
    week_series = build_trend_series(
        [(date(2026, 6, 3), Decimal("9"), 1)],
        period="7d",
        bucket="week",
    )
    assert week_series.points[0].bucket_label == "2026-W23"

    month_series = build_trend_series(
        [(date(2026, 6, 15), Decimal("9"), 1)],
        period="90d",
        bucket="month",
    )
    assert month_series.points[0].bucket_label == "2026-06"


def test_build_trend_series_data_ready_requires_two_nonempty_buckets() -> None:
    sparse = build_trend_series(
        [(date(2026, 6, 1), None, 0)],
        period="30d",
        bucket="day",
    )
    assert sparse.data_ready is False

    ready = build_trend_series(
        [
            (date(2026, 6, 1), Decimal("1.00"), 1),
            (date(2026, 6, 2), None, 0),
            (date(2026, 6, 3), Decimal("2.00"), 4),
        ],
        period="30d",
        bucket="day",
    )
    assert ready.data_ready is True


def test_build_trend_series_empty_rows() -> None:
    series = build_trend_series([], period="30d", bucket="day")
    assert series == TrendSeries(
        points=[],
        currency="EUR",
        bucket="day",
        period="30d",
        data_ready=False,
    )


def test_build_trend_series_preserves_none_avg() -> None:
    series = build_trend_series(
        [(date(2026, 6, 1), None, 0)],
        period="30d",
        bucket="day",
    )
    assert series.points == [
        TrendPoint(
            bucket_label="2026-06-01",
            bucket_start=date(2026, 6, 1),
            avg_price_eur=None,
            sample_size=0,
        ),
    ]


def test_trend_route_registered() -> None:
    paths = {route.path for route in app.routes}
    assert "/api/markets/trend" in paths


@pytest.mark.asyncio
async def test_trend_route_returns_model(client, trend_auth_override) -> None:
    with patch(
        "app.modules.visualisation_calc.api.read_price_trend",
        new_callable=AsyncMock,
        return_value=[],
    ) as read_mock:
        resp = await client.get("/api/markets/trend")
    assert resp.status_code == 200
    assert resp.json() == {
        "points": [],
        "currency": "EUR",
        "bucket": "day",
        "period": "30d",
        "data_ready": False,
    }
    read_mock.assert_awaited_once()

    with patch(
        "app.modules.visualisation_calc.api.read_price_trend",
        new_callable=AsyncMock,
        return_value=[(date(2026, 6, 1), Decimal("10.5"), 2)],
    ):
        resp = await client.get(
            "/api/markets/trend",
            params={"period": "7d", "bucket": "week", "country_code": "de"},
        )
    assert resp.status_code == 200
    assert resp.json()["points"][0]["avg_price_eur"] == "10.50"
    assert resp.json()["data_ready"] is False
