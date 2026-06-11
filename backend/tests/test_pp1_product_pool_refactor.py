"""
PP1 product_pool refactor invariants (no DB/HTTP).

Verifies:
1. _row_to_pool_item returns canonical-only fields. The legacy duplicates
   (current_price, last_scraped_at, price_change_pct_24h) and always-None
   placeholders (original_price, price_change_pct_7d/30d, volatility_30d)
   are gone (Rule 3).
2. get_pool_stats returns only the canonical 5 keys. The duplicate stats
   (total_marketplaces, products_with_price, last_discovery_at, message)
   are gone.
3. PoolStatsResponse declares exactly the 5 canonical fields; the "legacy
   keys (optional)" block was removed.
4. /pool/products, /pool/categories, /pool/marketplace-stats, /pool/stats,
   /pool/search, /markets/overview are all registered AND have response_model
   set (no untyped routes left).
5. Orphan schemas PoolCategoriesResponse and MarketplaceStatsItem are gone;
   PoolCategorySummary, PoolProductItem, PoolRecentPricePoint, PoolCategoryItem,
   PoolSearchResponse are present.
6. Stray init.py / placeholder models.py are gone; __init__.py is present.
7. search_products still delegates to list_products (single SQL path).
8. _apply_display_currency reads `price` (canonical) not `current_price`.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

from app.main import app
from app.modules.product_pool import schemas as pool_schemas
from app.modules.product_pool.schemas import (
    PoolCategoryItem,
    PoolCategorySummary,
    PoolProductItem,
    PoolProductsResponse,
    PoolRecentPricePoint,
    PoolSearchResponse,
    PoolStatsResponse,
)
from app.modules.product_pool.service import ProductPoolService, _row_to_pool_item

POOL_DIR = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "modules"
    / "product_pool"
)

FORBIDDEN_POOL_ITEM_FIELDS: tuple[str, ...] = (
    "current_price",
    "last_scraped_at",
    "price_change_pct_24h",
    "original_price",
    "price_change_pct_7d",
    "price_change_pct_30d",
    "volatility_30d",
)

REQUIRED_POOL_ITEM_FIELDS: tuple[str, ...] = (
    "id",
    "marketplace_id",
    "product_id",
    "title",
    "image_url",
    "url",
    "marketplace_name",
    "marketplace_domain",
    "marketplace_code",
    "country_code",
    "price",
    "currency",
    "price_eur",
    "price_change_pct",
    "in_stock",
    "last_checked_at",
    "status",
    "is_active",
    "recent_prices",
    "display_price",
    "display_currency",
    "conversion_available",
    "local_currency_resolution",
    "local_currency_unavailable",
)

FORBIDDEN_POOL_STATS_KEYS: tuple[str, ...] = (
    "total_marketplaces",
    "products_with_price",
    "last_discovery_at",
    "message",
)

REQUIRED_POOL_STATS_KEYS: frozenset[str] = frozenset(
    {
        "total_products",
        "total_listings",
        "marketplaces_count",
        "listings_with_price",
        "last_updated",
    }
)

DEAD_ORPHAN_SCHEMAS: tuple[str, ...] = (
    "PoolCategoriesResponse",
    "MarketplaceStatsItem",
)


def _sample_row() -> dict:
    """Mapping shape produced by ProductPoolService._base_listing_stmt."""
    return {
        "id": "00000000-0000-0000-0000-00000000aaaa",
        "product_id": "00000000-0000-0000-0000-00000000bbbb",
        "marketplace_id": "00000000-0000-0000-0000-00000000cccc",
        "title": "Sample",
        "image_url": None,
        "url": "https://example.test/x",
        "marketplace_name": "Example",
        "marketplace_domain": "example.test",
        "marketplace_code": "example_test",
        "country_code": "EU",
        "price": 9.99,
        "currency": "EUR",
        "price_eur": 9.99,
        "price_change_pct": 1.25,
        "in_stock": True,
        "last_checked_at": None,
        "is_active": True,
    }


def test_row_to_pool_item_drops_legacy_duplicates_and_placeholders() -> None:
    item = _row_to_pool_item(_sample_row())
    leaked = {k for k in FORBIDDEN_POOL_ITEM_FIELDS if k in item}
    assert not leaked, (
        f"Rule 3 violation: _row_to_pool_item still emits {sorted(leaked)}. "
        "Canonical readers are price / last_checked_at / price_change_pct."
    )


def test_row_to_pool_item_keeps_canonical_fields() -> None:
    item = _row_to_pool_item(_sample_row())
    missing = {k for k in REQUIRED_POOL_ITEM_FIELDS if k not in item}
    assert not missing, (
        f"_row_to_pool_item lost canonical field(s) {sorted(missing)}."
    )
    assert item["price"] == 9.99
    assert item["price_change_pct"] == 1.25
    assert item["last_checked_at"] is None


def test_apply_display_currency_reads_canonical_price() -> None:
    """The display-currency converter must read `price`, not the legacy
    `current_price`. Otherwise it silently sees None for every row."""
    source = inspect.getsource(ProductPoolService._apply_display_currency)
    assert 'item.get("price")' in source, (
        "_apply_display_currency must read the canonical `price` field."
    )
    assert "current_price" not in source, (
        "_apply_display_currency still references legacy `current_price`."
    )


def test_pool_stats_response_is_canonical_only() -> None:
    fields = set(PoolStatsResponse.model_fields.keys())
    assert fields == REQUIRED_POOL_STATS_KEYS, (
        f"PoolStatsResponse drifted; got {sorted(fields)}, "
        f"expected {sorted(REQUIRED_POOL_STATS_KEYS)}"
    )
    for forbidden in FORBIDDEN_POOL_STATS_KEYS:
        assert forbidden not in fields, (
            f"PoolStatsResponse still carries duplicate `{forbidden}`."
        )


def test_get_pool_stats_returns_canonical_only() -> None:
    """Drive get_pool_stats with a fake db.scalar to assert the dict shape
    without touching Postgres."""
    import asyncio
    from unittest.mock import AsyncMock

    fake_db = AsyncMock()
    fake_db.scalar = AsyncMock(side_effect=[11, 5, 3, 2, None])
    svc = ProductPoolService.__new__(ProductPoolService)
    svc.db = fake_db

    result = asyncio.run(svc.get_pool_stats())

    assert set(result.keys()) == REQUIRED_POOL_STATS_KEYS, (
        f"get_pool_stats returns drifted keys: {sorted(result.keys())}"
    )
    assert result == {
        "total_products": 5,
        "total_listings": 11,
        "marketplaces_count": 3,
        "listings_with_price": 2,
        "last_updated": None,
    }


def test_orphan_schemas_gone() -> None:
    for name in DEAD_ORPHAN_SCHEMAS:
        assert not hasattr(pool_schemas, name), (
            f"Orphan schema {name!r} still exposed by product_pool.schemas."
        )


def test_live_schemas_present() -> None:
    """Sanity: schemas that we kept are still importable."""
    for cls in (
        PoolCategorySummary,
        PoolCategoryItem,
        PoolProductItem,
        PoolProductsResponse,
        PoolRecentPricePoint,
        PoolSearchResponse,
        PoolStatsResponse,
    ):
        assert cls.__name__ in dir(pool_schemas), f"Missing {cls.__name__}"


def test_artefacts_replaced_with_proper_package_init() -> None:
    files = {p.name for p in POOL_DIR.iterdir() if p.is_file()}
    assert "init.py" not in files, "Stray 1-byte init.py must be deleted."
    assert "models.py" not in files, "Placeholder models.py must be deleted."
    assert "__init__.py" in files, "Proper package __init__.py must exist."
    init_source = (POOL_DIR / "__init__.py").read_text(encoding="utf-8").strip()
    assert init_source.startswith('"""'), "__init__.py must carry a docstring."


def _route_for(path: str, method: str = "GET"):
    for route in app.routes:
        if getattr(route, "path", "") == path and method in getattr(route, "methods", set()):
            return route
    return None


@pytest.mark.parametrize(
    "path,expected_class_name",
    [
        ("/api/markets/overview", "PoolProductsResponse"),
        ("/api/pool/products", "PoolProductsResponse"),
        ("/api/pool/categories", "PoolCategoryItem"),
        ("/api/pool/marketplace-stats", "PoolCategorySummary"),
        ("/api/pool/stats", "PoolStatsResponse"),
        ("/api/pool/search", "PoolSearchResponse"),
    ],
)
def test_routes_are_typed(path: str, expected_class_name: str) -> None:
    route = _route_for(path)
    assert route is not None, f"Route missing: {path}"
    rm = getattr(route, "response_model", None)
    assert rm is not None, f"Route {path} has no response_model after PP1."
    rendered = repr(rm)
    assert expected_class_name in rendered, (
        f"Route {path} response_model mismatch: got {rendered!r}, "
        f"expected to contain class {expected_class_name!r}."
    )


def test_overview_and_pool_products_both_live() -> None:
    """Both pages-on-one-source pattern: /markets/overview and /pool/products
    must coexist and both delegate to list_products."""
    assert _route_for("/api/markets/overview") is not None
    assert _route_for("/api/pool/products") is not None

    from app.modules.product_pool.api import get_overview, list_pool_products

    for handler in (get_overview, list_pool_products):
        src = inspect.getsource(handler)
        assert "list_products(" in src, (
            f"{handler.__name__} no longer delegates to list_products."
        )


def test_search_reuses_list_products() -> None:
    """search_products must remain a thin wrapper over list_products
    (no forked SQL path)."""
    src = inspect.getsource(ProductPoolService.search_products)
    assert "self.list_products(" in src, (
        "search_products must delegate to list_products."
    )
