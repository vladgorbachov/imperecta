"""P4 KPI history assembly: running pool total, honest missing days (no DB)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.visualisation_calc.kpi_history.service import build_kpi_history

D1, D2, D3 = date(2026, 9, 10), date(2026, 9, 12), date(2026, 9, 14)


def test_series_carry_only_days_with_activity():
    price_rows = [
        (D1, 10, 2, Decimal("3.5")),
        (D3, 20, 0, None),
    ]
    out = build_kpi_history(price_rows, 0, [], days=7)
    assert [p.date for p in out.series.updated_24h] == [D1, D3]
    assert [p.value for p in out.series.changed_gt5] == [Decimal(2), Decimal(0)]
    # a day whose avg is undefined is absent from the volatility series
    assert [p.date for p in out.series.avg_volatility] == [D1]
    assert out.series.avg_volatility[0].value == Decimal("3.5000")


def test_total_pool_is_running_sum_over_entries():
    out = build_kpi_history([], 100, [(D1, 5), (D2, 0), (D3, 7)], days=7)
    values = [(p.date, p.value) for p in out.series.total_pool]
    assert values == [
        (D1, Decimal(105)),
        (D2, Decimal(105)),
        (D3, Decimal(112)),
    ]


def test_empty_window_is_honest_empty():
    out = build_kpi_history([], 0, [], days=7)
    assert out.series.total_pool == []
    assert out.series.updated_24h == []
    assert out.series.changed_gt5 == []
    assert out.series.avg_volatility == []


def test_visible_pool_predicate_matches_partial_index_form() -> None:
    """The reads must render bare ``is_active`` (not ``.is_(True)`` ->
    ``IS TRUE``): the planner cannot prove IS TRUE against the
    ``WHERE is_active = TRUE`` predicate of idx_listing_pool_entry_created
    and falls back to a 1.4M-row seq scan (verified on prod, 2026-09-18)."""
    import inspect

    from app.modules.visualisation_calc.kpi_history import read as kpi_read

    source = inspect.getsource(kpi_read)
    assert "is_active.is_(True)" not in source
    assert "FactListing.is_active," in source
