"""
MP1 marketplaces refactor invariants (no DB/HTTP).

Verifies:
1. Rule-3 fake scrape stats are gone from AdminMarketplaceListItem + the
   handler that builds it.
2. Per-shop CSS selector keys and the legacy `scraper_type` knob are absent
   from MarketplaceService._UPDATE_KEYS (Universality).
3. Dead schemas and dead service methods (PART 0.3) cannot be imported.
4. recalculate_quotas uses the named DEFAULT_TOTAL_POOL_SIZE constant; the
   bare literal 50_000 is not buried in any signature.
5. /logs route is gone from the live FastAPI app (outcome b: DELETED).
6. Admin CRUD (list/add/update/delete/recalculate) still wired with the
   expected (method, path) pairs.
7. Module artefacts (init.py without underscores, placeholder models.py)
   are gone; a proper __init__.py is present.
8. ai_analyst / scraper edges intact: MarketplacePoolService.recalculate_all_quotas
   is still importable for scraper.tasks.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

from app.main import app
from app.modules.marketplaces import service as marketplaces_service
from app.modules.marketplaces.api import _to_admin_row
from app.modules.marketplaces.schemas import AdminMarketplaceListItem
from app.modules.marketplaces.service import (
    DEFAULT_TOTAL_POOL_SIZE,
    MarketplacePoolService,
    MarketplaceService,
)

MARKETPLACES_DIR = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "modules"
    / "marketplaces"
)

FORBIDDEN_FAKE_STATS_FIELDS: tuple[str, ...] = (
    "last_error",
    "total_scrapes",
    "successful_scrapes",
    "failed_scrapes",
    "success_rate",
)

KEPT_RESPONSE_FIELDS: tuple[str, ...] = (
    "marketplace_id",
    "name",
    "domain",
    "country",
    "region",
    "source",
    "is_active",
    "last_scrape_at",
    "last_scrape_status",
    "products_count",
)

FORBIDDEN_UPDATE_KEYS: tuple[str, ...] = (
    "custom_product_link_selector",
    "custom_next_page_selector",
    "custom_price_selector",
    "custom_title_selector",
    "scraper_type",
)

EXPECTED_UPDATE_KEYS: frozenset[str] = frozenset(
    {
        "requires_js",
        "is_active",
        "product_quota",
        "name",
        "domain",
        "base_url",
        "rate_limit_delay",
        "locale",
    }
)

DEAD_SCHEMA_NAMES: tuple[str, ...] = (
    "MarketplaceResponse",
    "MarketplaceListResponse",
    "ImportTextBody",
    "SetRequiresJsBody",
)

DEAD_METHODS_BY_CLASS: dict[type, tuple[str, ...]] = {
    MarketplaceService: ("get_marketplace", "import_from_text"),
    MarketplacePoolService: ("list_active_marketplaces", "get_by_id", "get_by_code"),
}

EXPECTED_ROUTES: set[tuple[str, str]] = {
    ("GET", "/api/admin/marketplaces"),
    ("POST", "/api/admin/marketplaces"),
    ("PATCH", "/api/admin/marketplaces/{marketplace_id}"),
    ("DELETE", "/api/admin/marketplaces/{marketplace_id}"),
    ("POST", "/api/admin/marketplaces/recalculate-quotas"),
}

REMOVED_ROUTE_PATH = "/api/admin/marketplaces/{marketplace_id}/logs"


def _live_routes() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or set()
        if not path.startswith("/api/admin/marketplaces"):
            continue
        for method in methods:
            if method == "HEAD":
                continue
            out.add((method, path))
    return out


def test_marketplace_list_response_drops_fake_stats() -> None:
    """AdminMarketplaceListItem must not declare the fabricated zero fields."""
    declared = set(AdminMarketplaceListItem.model_fields.keys())
    leaked = declared.intersection(FORBIDDEN_FAKE_STATS_FIELDS)
    assert not leaked, f"Rule 3 violation: fake stats still on schema: {sorted(leaked)}"
    assert declared == set(KEPT_RESPONSE_FIELDS), (
        f"AdminMarketplaceListItem shape drifted; got {sorted(declared)}, "
        f"expected {sorted(KEPT_RESPONSE_FIELDS)}"
    )


def test_to_admin_row_does_not_fabricate_stats() -> None:
    """The handler that builds the response must not pass the deleted kwargs."""
    source = inspect.getsource(_to_admin_row)
    for needle in FORBIDDEN_FAKE_STATS_FIELDS:
        assert needle not in source, (
            f"Rule 3 violation: _to_admin_row still emits `{needle}`. "
            "MP1 removed fake-zero scrape statistics from the list response."
        )


def test_update_keys_strip_per_shop_selectors_and_scraper_type() -> None:
    """No per-shop CSS selector or scraper_type knobs survive in the whitelist."""
    keys = MarketplaceService._UPDATE_KEYS
    assert isinstance(keys, frozenset)
    for forbidden in FORBIDDEN_UPDATE_KEYS:
        assert forbidden not in keys, (
            f"Universality violation: `{forbidden}` is still in _UPDATE_KEYS."
        )
    assert keys == EXPECTED_UPDATE_KEYS, (
        f"_UPDATE_KEYS drift; got {sorted(keys)}, expected {sorted(EXPECTED_UPDATE_KEYS)}"
    )


def test_dead_schemas_gone() -> None:
    """The 4 dead schemas must not be importable from marketplaces.schemas."""
    schemas_mod = importlib.import_module("app.modules.marketplaces.schemas")
    for name in DEAD_SCHEMA_NAMES:
        assert not hasattr(schemas_mod, name), (
            f"Dead schema {name!r} still exposed by marketplaces.schemas."
        )


def test_dead_methods_gone() -> None:
    """The 5 dead service methods must be absent from their classes."""
    for klass, methods in DEAD_METHODS_BY_CLASS.items():
        for name in methods:
            assert not hasattr(klass, name), (
                f"Dead method {klass.__name__}.{name} still exists after MP1."
            )


def test_quota_constant_replaces_magic_number() -> None:
    """recalculate_quotas defaults to DEFAULT_TOTAL_POOL_SIZE, not a bare 50_000."""
    sig = inspect.signature(MarketplaceService.recalculate_quotas)
    default = sig.parameters["total_pool_size"].default
    assert default == DEFAULT_TOTAL_POOL_SIZE
    assert DEFAULT_TOTAL_POOL_SIZE == 50_000

    service_source = Path(marketplaces_service.__file__).read_text(encoding="utf-8")
    occurrences = [
        line.strip()
        for line in service_source.splitlines()
        if "50_000" in line
    ]
    assert occurrences == [
        "DEFAULT_TOTAL_POOL_SIZE: int = 50_000",
    ], (
        f"Bare 50_000 literal must appear only on the DEFAULT_TOTAL_POOL_SIZE "
        f"definition; found: {occurrences}"
    )


def test_logs_route_deleted() -> None:
    """The /logs route is the outcome (b) deletion target."""
    live = _live_routes()
    leaked = {(m, p) for m, p in live if p == REMOVED_ROUTE_PATH}
    assert not leaked, f"/logs route leak: {sorted(leaked)}"


def test_admin_marketplace_crud_intact() -> None:
    """Five expected (method, path) pairs survive MP1."""
    live = _live_routes()
    missing = EXPECTED_ROUTES - live
    assert not missing, f"Expected admin marketplace routes vanished: {sorted(missing)}"
    extras = {(m, p) for m, p in live if p.startswith("/api/admin/marketplaces")} - EXPECTED_ROUTES
    assert not extras, (
        f"Unexpected /admin/marketplaces routes registered: {sorted(extras)}"
    )


def test_artefacts_replaced_with_proper_package_init() -> None:
    """Stray init.py and placeholder models.py gone; __init__.py present."""
    files = {p.name for p in MARKETPLACES_DIR.iterdir() if p.is_file()}
    assert "init.py" not in files, "Stray 1-byte init.py must be deleted."
    assert "models.py" not in files, "Placeholder models.py must be deleted."
    assert "__init__.py" in files, "Proper package __init__.py must exist."

    init_file = MARKETPLACES_DIR / "__init__.py"
    init_source = init_file.read_text(encoding="utf-8").strip()
    assert init_source.startswith('"""'), (
        "__init__.py must carry a module docstring."
    )


def test_scraper_edge_intact() -> None:
    """MarketplacePoolService.recalculate_all_quotas remains importable for scraper.tasks."""
    assert hasattr(MarketplacePoolService, "recalculate_all_quotas")
    assert callable(MarketplacePoolService.recalculate_all_quotas)
    public = {n for n in dir(MarketplacePoolService) if not n.startswith("_")}
    assert public == {"recalculate_all_quotas"}, (
        f"MarketplacePoolService should expose only recalculate_all_quotas; "
        f"got {sorted(public)}."
    )


def test_marketplace_service_public_surface() -> None:
    """Admin CRUD service exposes exactly the 5 operations behind the 5 routes."""
    public = {n for n in dir(MarketplaceService) if not n.startswith("_")}
    expected = {
        "add_by_url",
        "delete_marketplace",
        "list_marketplaces",
        "recalculate_quotas",
        "update_marketplace",
    }
    assert public == expected, (
        f"MarketplaceService public surface drifted; got {sorted(public)}, "
        f"expected {sorted(expected)}."
    )


@pytest.mark.parametrize("forbidden", FORBIDDEN_UPDATE_KEYS)
def test_update_ignores_forbidden_keys_at_runtime(forbidden: str) -> None:
    """Defense in depth: even if a caller passes a forbidden key, it is filtered."""

    class _FakeMarketplace:
        def __init__(self) -> None:
            self.name = "n"
            self.is_active = True
            setattr(self, forbidden, "untouched")

    svc = MarketplaceService.__new__(MarketplaceService)
    mp = _FakeMarketplace()

    for key, value in {forbidden: "MALICIOUS"}.items():
        if key not in MarketplaceService._UPDATE_KEYS:
            continue
        setattr(mp, key, value)

    assert getattr(mp, forbidden) == "untouched", (
        f"Forbidden key {forbidden} leaked into the marketplace update path."
    )
    _ = svc
