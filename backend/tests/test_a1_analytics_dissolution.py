"""
A1 dissolution tests for the analytics module.

Framework-light invariants (no DB / no HTTP) that prove:

1. `app.modules.analytics` and every submodule import is gone.
2. All 9 previously-mounted analytics routes are unmounted (8 deleted in A1
   plus `/analytics/dashboard/summary` whose only live consumer moved to
   `/entitlements/usage`).
3. No dead analytics symbol survives anywhere in `app/` source
   (`ForecastService`, `BenchmarkService`, `AnalyticsKpiService`,
   `linear_regression`).
4. `/entitlements/usage` is mounted under the `/api` prefix and is served by
   `UsageService.get_usage`.
5. `UsageService.get_usage` returns the honest products-only shape; the
   `competitors` key is intentionally absent because no per-user competitor
   model exists yet (Rule 3: no fabrication).
6. The plan -> limit resolution path is the project's single source of truth
   (`app.entitlements.get_limit`), not a private invented constant.
"""

import importlib
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.entitlements import get_limit
from app.main import app
from app.modules.entitlements.api import router as entitlements_router
from app.modules.entitlements.service import UsageService

ANALYTICS_PATHS_DELETED: set[str] = {
    "/api/analytics/products/{product_id}/price-history",
    "/api/analytics/products/{product_id}/comparison",
    "/api/analytics/products/{product_id}/forecast",
    "/api/analytics/market-forecast",
    "/api/analytics/simulate",
    "/api/analytics/advanced-simulation",
    "/api/analytics/competitor-benchmark",
    "/api/analytics/comparison-matrix",
    "/api/analytics/dashboard/summary",
}

FORBIDDEN_ANALYTICS_SYMBOLS: tuple[str, ...] = (
    "ForecastService",
    "BenchmarkService",
    "AnalyticsKpiService",
    "linear_regression",
    "app.modules.analytics",
    "analytics.service",
    "analytics.schemas",
)

BACKEND_APP_DIR = Path(__file__).resolve().parents[1] / "app"


@pytest.mark.parametrize(
    "module_path",
    [
        "app.modules.analytics",
        "app.modules.analytics.api",
        "app.modules.analytics.service",
        "app.modules.analytics.schemas",
    ],
)
def test_analytics_module_dissolved(module_path: str) -> None:
    """The analytics package and its leaf modules no longer exist."""
    with pytest.raises(ImportError):
        importlib.import_module(module_path)


def test_no_analytics_routes_mounted_on_app() -> None:
    """Every previously-mounted analytics path is gone from the live app."""
    actual_paths = {getattr(route, "path", None) for route in app.routes}
    still_present = ANALYTICS_PATHS_DELETED & actual_paths
    assert not still_present, (
        f"A1 deletion failed - these analytics routes still exist: {sorted(still_present)}"
    )
    leftover_analytics = {p for p in actual_paths if p and p.startswith("/api/analytics")}
    assert not leftover_analytics, (
        f"No /api/analytics/* route should survive A1; found: {sorted(leftover_analytics)}"
    )


def test_no_dead_analytics_symbols_in_backend_source() -> None:
    """Grep guard over backend/app source for orphaned analytics references."""
    offenders: list[tuple[str, str]] = []
    for path in BACKEND_APP_DIR.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for needle in FORBIDDEN_ANALYTICS_SYMBOLS:
            if needle in text:
                offenders.append((str(path.relative_to(BACKEND_APP_DIR)), needle))
    assert not offenders, (
        "Dead analytics references remain in backend/app:\n"
        + "\n".join(f"  {p}: {needle}" for p, needle in offenders)
    )


def test_entitlements_usage_mounted_under_api_prefix() -> None:
    """`/api/entitlements/usage` is registered exactly once."""
    paths = [getattr(r, "path", None) for r in app.routes]
    assert paths.count("/api/entitlements/usage") == 1, (
        f"Expected exactly one /api/entitlements/usage mount, paths={sorted(p for p in paths if p)}"
    )


def test_entitlements_router_endpoint_calls_usage_service() -> None:
    """The mounted route is served by UsageService.get_usage and lives in the entitlements module."""
    usage_route = next(
        r for r in entitlements_router.routes if r.path == "/entitlements/usage"
    )
    src = inspect.getsource(usage_route.endpoint)
    assert "UsageService" in src
    assert "get_usage" in src
    assert usage_route.endpoint.__module__ == "app.modules.entitlements.api"


@pytest.mark.asyncio
async def test_usage_service_returns_products_only_shape() -> None:
    """get_usage returns products.{used,limit} and intentionally OMITS competitors."""
    fake_db = SimpleNamespace(scalar=AsyncMock(return_value=12))
    service = UsageService(fake_db, uuid4())

    result = await service.get_usage("starter")

    assert set(result.keys()) == {"products"}, (
        f"Response must contain only 'products' until a real competitor model exists, got: {sorted(result.keys())}"
    )
    assert "competitors" not in result, (
        "Rule 3 violation guard: competitors key must NOT be fabricated"
    )
    assert set(result["products"].keys()) == {"used", "limit"}
    assert result["products"]["used"] == 12
    assert result["products"]["limit"] == get_limit("starter", "products")
    assert fake_db.scalar.await_count == 1


@pytest.mark.asyncio
async def test_usage_service_handles_zero_products() -> None:
    """A user with no active products surfaces used=0, not NULL or absent."""
    fake_db = SimpleNamespace(scalar=AsyncMock(return_value=None))
    service = UsageService(fake_db, uuid4())

    result = await service.get_usage("starter")

    assert result["products"]["used"] == 0
    assert result["products"]["limit"] == get_limit("starter", "products")


@pytest.mark.asyncio
async def test_usage_service_per_plan_limits_are_real() -> None:
    """Each canonical plan resolves to its entitlements limit (no hardcoded 50)."""
    fake_db = SimpleNamespace(scalar=AsyncMock(return_value=1))
    service = UsageService(fake_db, uuid4())

    for plan in ("trial", "starter", "business", "pro", "enterprise"):
        result = await service.get_usage(plan)
        expected_limit = get_limit(plan, "products")
        assert result["products"]["limit"] == expected_limit, (
            f"Plan {plan!r} returned limit {result['products']['limit']!r}, expected {expected_limit!r}"
        )


@pytest.mark.asyncio
async def test_usage_service_unknown_plan_falls_back_to_free_tier_limit() -> None:
    """An unknown plan string must reuse entitlements.get_limit's FREE fallback (not crash, not 0)."""
    fake_db = SimpleNamespace(scalar=AsyncMock(return_value=3))
    service = UsageService(fake_db, uuid4())

    result = await service.get_usage("totally-unknown-plan")

    assert result["products"]["limit"] == get_limit("totally-unknown-plan", "products")
    assert result["products"]["limit"] > 0
