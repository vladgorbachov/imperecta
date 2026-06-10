"""
D1 dissolution tests for the dashboard module.

These tests are framework-light (no DB / no HTTP), matching the project's
structural-test style. They guard:

1. The `app.modules.dashboard` package and its submodules are gone.
2. The six empty handlers (3 under `/dashboard/*`, 3 under
   `/markets/*-analytics` + `/markets/opportunities`) are no longer mounted.
3. `/markets/overview` is preserved verbatim and is now served by the
   product_pool module (path + query params unchanged, frontend contract
   intact).
4. `MarketsService` (market_data facade) no longer exposes the C3 stubs.

A1 (analytics dissolution) further removes `/analytics/dashboard/summary`
and `AnalyticsKpiService`; the surviving frontend usage consumer moves to
`/entitlements/usage`. Those invariants live in
`test_a1_analytics_dissolution.py`.
"""

import importlib
import inspect
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.main import app
from app.modules.market_data.facade import MarketsService
from app.modules.product_pool.api import (
    OVERVIEW_SORT,
    markets_overview_router,
    router as pool_router,
)

DELETED_PATHS: set[str] = {
    "/api/dashboard/kpi",
    "/api/dashboard/anomalies",
    "/api/dashboard/aggregate-trend",
    "/api/markets/category-analytics",
    "/api/markets/marketplace-analytics",
    "/api/markets/opportunities",
}

OVERVIEW_QUERY_PARAMS: set[str] = {
    "sort",
    "search",
    "marketplace_id",
    "limit",
    "offset",
    "display_currency",
}

OVERVIEW_RESPONSE_KEYS: set[str] = {"items", "total", "limit", "offset"}


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


def test_overview_route_owned_by_product_pool() -> None:
    """`/markets/overview` lives on product_pool's markets_overview_router (not dashboard)."""
    overview_paths = {route.path for route in markets_overview_router.routes}
    assert "/markets/overview" in overview_paths, (
        "product_pool.markets_overview_router must publish /markets/overview"
    )
    pool_paths = {route.path for route in pool_router.routes}
    assert "/markets/overview" not in pool_paths, (
        "/markets/overview must not be on the /pool router"
    )


def test_overview_query_params_preserved() -> None:
    """Frontend marketsApi.getOverview depends on exact query params + sort whitelist."""
    overview_route = next(
        route for route in markets_overview_router.routes if route.path == "/markets/overview"
    )
    signature = inspect.signature(overview_route.endpoint)
    actual_params = set(signature.parameters.keys())
    missing = OVERVIEW_QUERY_PARAMS - actual_params
    assert not missing, f"/markets/overview lost query params: {sorted(missing)}"
    assert set(OVERVIEW_SORT) == {"volatile", "trending", "gainers", "losers", "recent"}


def test_overview_app_route_is_under_api_prefix() -> None:
    """The mounted /markets/overview endpoint is reachable under the /api prefix."""
    actual_paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/markets/overview" in actual_paths


@pytest.mark.asyncio
async def test_overview_invokes_product_pool_list_products(monkeypatch: pytest.MonkeyPatch) -> None:
    """/markets/overview is a thin caller of ProductPoolService.list_products with preserved shape."""
    captured: dict[str, object] = {}

    async def fake_list_products(self, **kwargs):  # noqa: ARG001
        captured.update(kwargs)
        return [{"id": "sentinel"}], 1

    monkeypatch.setattr(
        "app.modules.product_pool.service.ProductPoolService.list_products",
        fake_list_products,
    )

    overview_route = next(
        route for route in markets_overview_router.routes if route.path == "/markets/overview"
    )
    fake_user = SimpleNamespace(id=uuid4(), is_superuser=False)
    fake_db = SimpleNamespace()

    response = await overview_route.endpoint(
        current_user=fake_user,
        db=fake_db,
        sort="not-a-real-sort",
        search=None,
        marketplace_id=None,
        limit=25,
        offset=0,
        display_currency="EUR",
    )

    assert set(response.keys()) == OVERVIEW_RESPONSE_KEYS
    assert response == {"items": [{"id": "sentinel"}], "total": 1, "limit": 25, "offset": 0}
    assert captured["sort"] == "volatile", "Invalid sort must fall back to 'volatile'"
    assert captured["limit"] == 25
    assert captured["offset"] == 0
    assert captured["display_currency"] == "EUR"
    assert captured["include_blocked_countries"] is False


@pytest.mark.parametrize(
    "stub_name",
    ["get_category_analytics", "get_marketplace_analytics", "get_opportunities"],
)
def test_market_data_c3_stubs_removed(stub_name: str) -> None:
    """MarketsService no longer carries the dashboard C3 analytics stubs."""
    assert not hasattr(MarketsService, stub_name), (
        f"MarketsService.{stub_name} must be removed in D1 (had no callers after dashboard dissolution)"
    )
