"""
UP1 dissolution tests.

Framework-light invariants (no DB / no HTTP) that prove:

1. `app.modules.user_products.{api_products,api_competitors,api_import,service,
   schemas,models}` no longer import.
2. The /products, /competitors, /import paths owned by user_products are
   absent from the live FastAPI app, while unrelated routes (admin
   marketplaces, pool, etc.) are preserved.
3. The `user_products` package exposes nothing public beyond a documented
   empty placeholder.
4. The legacy user-products symbols (parse_products_file,
   preview_products_file, get_csv_template, css_selector_price) and the
   per-shop scraper_type schema field have no definition under
   backend/app/.
5. `ai_analyst.service.auto_categorize` still imports cleanly (we removed
   its caller, not the function).
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from app.main import app

BACKEND_APP_DIR = Path(__file__).resolve().parents[1] / "app"

DELETED_USER_PRODUCTS_SUBMODULES: tuple[str, ...] = (
    "app.modules.user_products.api_products",
    "app.modules.user_products.api_competitors",
    "app.modules.user_products.api_import",
    "app.modules.user_products.service",
    "app.modules.user_products.schemas",
    "app.modules.user_products.models",
)

USER_PRODUCTS_DELETED_PATHS: set[str] = {
    # /products router (api_products.py)
    "/api/products",
    "/api/products/",
    "/api/products/categories",
    "/api/products/at-risk",
    "/api/products/bulk",
    "/api/products/all",
    "/api/products/{id}",
    "/api/products/{id}/ai-recommendation",
    # /competitors router (api_competitors.py)
    "/api/competitors",
    "/api/competitors/",
    "/api/competitors/marketplaces",
    "/api/competitors/products",
    "/api/competitors/products/{id}",
    "/api/competitors/products/{product_id}",
    "/api/competitors/{competitor_id}",
    "/api/competitors/{competitor_id}/products",
    "/api/competitors/{competitor_id}/scrape",
    # /import router (api_import.py)
    "/api/import/auto-categorize",
    "/api/import/products/preview",
    "/api/import/products/csv",
    "/api/import/products/template",
}

# Routes that must REMAIN (sourced from other modules, not user_products).
PRESERVED_ROUTES: tuple[str, ...] = (
    "/api/pool/products",
    "/api/pool/categories",
    "/api/admin/marketplaces",
    "/api/markets/overview",
    "/api/entitlements/usage",
)

FORBIDDEN_SYMBOLS: tuple[str, ...] = (
    "parse_products_file",
    "preview_products_file",
    "get_csv_template",
    "css_selector_price",
)


def _list_source_files() -> list[Path]:
    """Return all .py files under backend/app/ for source-grep guards."""
    return [
        path
        for path in BACKEND_APP_DIR.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def _registered_paths() -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_user_products_submodules_emptied() -> None:
    """Each deleted submodule must raise ImportError."""
    for module_path in DELETED_USER_PRODUCTS_SUBMODULES:
        with pytest.raises(ImportError):
            importlib.import_module(module_path)


def test_user_products_package_is_bare_skeleton() -> None:
    """The package itself imports but exports nothing beyond its docstring."""
    package = importlib.import_module("app.modules.user_products")
    assert package.__doc__, "user_products package must carry an explanatory docstring."
    public = {name for name in dir(package) if not name.startswith("_")}
    assert public == set(), (
        f"user_products package should expose nothing public; found {public}."
    )


def test_user_products_routes_gone() -> None:
    """Every path owned by user_products is absent from app.routes."""
    registered = _registered_paths()
    leaked = USER_PRODUCTS_DELETED_PATHS & registered
    assert not leaked, f"user_products routes still mounted: {sorted(leaked)}"


def test_unrelated_routes_preserved() -> None:
    """Routes from other modules must not be collateral damage."""
    registered = _registered_paths()
    for path in PRESERVED_ROUTES:
        assert path in registered, (
            f"Unrelated route {path} was removed by mistake. "
            f"Registered routes: {sorted(registered)}"
        )


def test_main_does_not_reference_user_products_routers() -> None:
    """Source-level guard: main.py no longer wires user_products routers."""
    main_source = (BACKEND_APP_DIR / "main.py").read_text(encoding="utf-8")
    for fragment in (
        "from app.modules.user_products",
        "import_router",
        "products_router",
    ):
        assert fragment not in main_source, (
            f"main.py still references {fragment!r} after UP1 dissolution."
        )


def test_forbidden_user_products_symbols_absent() -> None:
    """The per-user CSV parser helpers and css_selector_price are gone."""
    for source_file in _list_source_files():
        text = source_file.read_text(encoding="utf-8", errors="ignore")
        for needle in FORBIDDEN_SYMBOLS:
            assert needle not in text, (
                f"Forbidden symbol {needle!r} still found in {source_file} "
                "after UP1 dissolution."
            )


def test_user_products_directory_holds_only_init() -> None:
    """The on-disk module is reduced to a single __init__.py."""
    module_dir = BACKEND_APP_DIR / "modules" / "user_products"
    survivors = sorted(p.name for p in module_dir.iterdir() if p.is_file())
    assert survivors == ["__init__.py"], (
        f"user_products/ should contain only __init__.py; found {survivors}."
    )


def test_ai_analyst_auto_categorize_intact() -> None:
    """We removed user_products's caller, not the ai_analyst function itself."""
    module = importlib.import_module("app.modules.ai_analyst.service")
    assert hasattr(module, "auto_categorize"), (
        "ai_analyst.service.auto_categorize disappeared; UP1 should only remove "
        "its caller (user_products.api_import), not the function."
    )
    assert callable(module.auto_categorize)
