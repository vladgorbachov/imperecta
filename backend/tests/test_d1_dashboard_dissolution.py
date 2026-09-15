"""
D1 dissolution tests for the dashboard module.

These tests are framework-light (no DB / no HTTP), matching the project's
structural-test style. They guard:

1. The `app.modules.dashboard` package and its submodules are gone.
2. The six empty handlers (3 under `/dashboard/*`, 3 under
   `/markets/*-analytics` + `/markets/opportunities`) are no longer mounted.
3. `/markets/overview` is RETIRED (UI redesign V1-V6 moved the catalog to
   /products -> GET /pool/products; route-audit ritual run 2026-09-16:
   the only remaining FE reference was a test mock).
4. `MarketsService` (market_data facade) no longer exposes the C3 stubs.

A1 (analytics dissolution) further removes `/analytics/dashboard/summary`
and `AnalyticsKpiService`; the surviving frontend usage consumer moves to
`/entitlements/usage`. Those invariants live in
`test_a1_analytics_dissolution.py`.
"""

import importlib
import inspect

import pytest

from app.main import app
from app.modules.market_data.facade import MarketsService
from app.modules.product_pool.api import router as pool_router

DELETED_PATHS: set[str] = {
    "/api/markets/overview",
    "/api/markets/ticker",
    "/api/dashboard/kpi",
    "/api/dashboard/anomalies",
    "/api/dashboard/aggregate-trend",
    "/api/markets/category-analytics",
    "/api/markets/marketplace-analytics",
    "/api/markets/opportunities",
}



@pytest.mark.parametrize(
    "module_path",
    [
        "app.modules.dashboard",
        "app.modules.dashboard.api",
        "app.modules.dashboard.service",
        "app.modules.dashboard.schemas",
    ],
)
def test_dashboard_module_dissolved(module_path: str) -> None:
    """The dashboard package and its leaf modules no longer exist."""
    with pytest.raises(ImportError):
        importlib.import_module(module_path)


def test_main_does_not_import_dashboard_router() -> None:
    """app.main must not pull in any dashboard symbol after D1."""
    main_src = inspect.getsource(importlib.import_module("app.main"))
    forbidden = (
        "from app.modules.dashboard",
        "import app.modules.dashboard",
        "dashboard_router",
        "markets_dashboard_router",
        "DashboardService",
    )
    for needle in forbidden:
        assert needle not in main_src, (
            f"app/main.py still references dashboard symbol: {needle}"
        )


def test_deleted_routes_absent_from_app() -> None:
    """All six retired handlers are unmounted."""
    actual_paths = {getattr(route, "path", None) for route in app.routes}
    still_present = DELETED_PATHS & actual_paths
    assert not still_present, (
        f"D1 deletion failed - these routes are still registered: {sorted(still_present)}"
    )


def test_overview_and_ticker_retired_from_product_pool_and_market_data() -> None:
    """The retired dashboard endpoints are not published by any surviving router."""
    from app.modules.market_data.api import router as market_data_router

    pool_paths = {route.path for route in pool_router.routes}
    market_paths = {route.path for route in market_data_router.routes}
    assert "/markets/overview" not in pool_paths | market_paths
    assert "/markets/ticker" not in pool_paths | market_paths
    assert "/pool/products" in pool_paths, "the replacement catalog read must stay"


@pytest.mark.parametrize(
    "stub_name",
    ["get_category_analytics", "get_marketplace_analytics", "get_opportunities"],
)
def test_market_data_c3_stubs_removed(stub_name: str) -> None:
    """MarketsService no longer carries the dashboard C3 analytics stubs."""
    assert not hasattr(MarketsService, stub_name), (
        f"MarketsService.{stub_name} must be removed in D1 (had no callers after dashboard dissolution)"
    )
