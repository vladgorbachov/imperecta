"""Pure-logic tests for the Slice E volatility submodule (no DB)."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from app.modules.visualisation_calc.volatility.service import (
    MIN_OBSERVATIONS,
    _listing_volatility_pct,
    build_volatility_kpi,
)

L1 = uuid4()
L2 = uuid4()


def _rows(listing, prices, start=20260901):
    return [(listing, start + i, Decimal(str(p))) for i, p in enumerate(prices)]


def test_constant_prices_have_zero_volatility() -> None:
    kpi = build_volatility_kpi(
        _rows(L1, [10, 10, 10, 10]), period="30d", window_days=30
    )
    assert kpi.data_ready is True
    assert kpi.listings_covered == 1
    assert kpi.avg_volatility_pct == Decimal("0.0000")


def test_known_series_volatility() -> None:
    # returns: +10%, -10% -> sample stddev = sqrt(((10-0)^2 + (-10-0)^2)/1) ...
    # mean = 0.9090..., stddev computed decimal-exactly by the service
    vol = _listing_volatility_pct([Decimal(100), Decimal(110), Decimal(99)])
    assert vol is not None
    # returns are +10 and -10 pct; mean 0, sample variance 200, stddev ~14.142
    assert abs(vol - Decimal(200).sqrt()) < Decimal("0.01")


def test_too_few_observations_is_honest_empty() -> None:
    kpi = build_volatility_kpi(_rows(L1, [10, 11]), period="7d", window_days=7)
    assert kpi.avg_volatility_pct is None
    assert kpi.listings_covered == 0
    assert kpi.data_ready is False
    assert MIN_OBSERVATIONS == 3


def test_average_across_listings_skips_short_series() -> None:
    rows = _rows(L1, [10, 10, 10]) + _rows(L2, [5, 6])
    kpi = build_volatility_kpi(rows, period="30d", window_days=30)
    assert kpi.listings_covered == 1
    assert kpi.avg_volatility_pct == Decimal("0.0000")


def test_zero_price_points_do_not_crash() -> None:
    kpi = build_volatility_kpi(
        _rows(L1, [0, 0, 0, 0]), period="30d", window_days=30
    )
    assert kpi.avg_volatility_pct is None
    assert kpi.data_ready is False
