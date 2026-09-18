"""Tests for the Slice E volatility submodule (no DB).

The per-listing math moved into SQL (volatility/read.py) when the pool grew to
1.4M listings — streaming every deduped daily price row into Python could not
survive harvest volume. The pure layer now only rounds and shapes the KPI, so
these tests cover that plus the semantic invariants of the SQL text itself.
"""

from __future__ import annotations

from decimal import Decimal

from app.modules.visualisation_calc.volatility.read import _VOLATILITY_SQL
from app.modules.visualisation_calc.volatility.service import (
    MIN_OBSERVATIONS,
    build_volatility_kpi,
)


def test_kpi_quantizes_average_to_four_decimals() -> None:
    kpi = build_volatility_kpi(
        Decimal("14.14213562"), 3, period="30d", window_days=30
    )
    assert kpi.avg_volatility_pct == Decimal("14.1421")
    assert kpi.listings_covered == 3
    assert kpi.window_days == 30
    assert kpi.period == "30d"
    assert kpi.data_ready is True


def test_zero_covered_listings_is_honest_empty() -> None:
    kpi = build_volatility_kpi(None, 0, period="7d", window_days=7)
    assert kpi.avg_volatility_pct is None
    assert kpi.listings_covered == 0
    assert kpi.data_ready is False
    assert MIN_OBSERVATIONS == 3


def test_zero_volatility_with_coverage_is_data_ready() -> None:
    kpi = build_volatility_kpi(Decimal("0"), 1, period="30d", window_days=30)
    assert kpi.avg_volatility_pct == Decimal("0.0000")
    assert kpi.data_ready is True


def test_sql_dedupes_to_latest_scrape_per_listing_day() -> None:
    assert "DISTINCT ON (fp.listing_id, fp.date_id)" in _VOLATILITY_SQL
    assert "fp.scraped_at DESC" in _VOLATILITY_SQL


def test_sql_keeps_visible_product_pool_grain() -> None:
    # Bare `fl.is_active`, not `IS TRUE`: the planner cannot prove the
    # IS TRUE form against `WHERE is_active = TRUE` partial-index predicates.
    assert "WHERE fl.is_active\n" in _VOLATILITY_SQL
    assert "IS TRUE" not in _VOLATILITY_SQL
    assert "fl.page_role = 'product'" in _VOLATILITY_SQL
    assert "fp.price_eur IS NOT NULL" in _VOLATILITY_SQL


def test_sql_volatility_semantics_match_former_python_calc() -> None:
    """Sample stddev of consecutive pct returns; zero-previous pairs skipped;
    >= MIN_OBSERVATIONS daily points and >= 2 usable returns per listing."""
    assert "stddev_samp(ret_pct)" in _VOLATILITY_SQL
    assert "WHEN lag(price_eur) OVER w <> 0" in _VOLATILITY_SQL
    assert "n_points >= :min_observations" in _VOLATILITY_SQL
    assert "HAVING count(ret_pct) >= 2" in _VOLATILITY_SQL
    assert "avg(vol_pct)" in _VOLATILITY_SQL
