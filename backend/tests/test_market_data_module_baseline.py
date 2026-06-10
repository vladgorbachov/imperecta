"""
Structural baseline for the market_data module (M1 refactor pass).

These tests are framework-light and have no DB/network requirements: they
guard the module's import surface, the public router shape, and the
provider->service dependency-inversion fix introduced in M1.
"""

import importlib
import pkgutil
import re
from pathlib import Path

import pytest

import app.modules.market_data.providers as providers_pkg
from app.modules.market_data import api as market_data_api

PROVIDERS_DIR = Path(providers_pkg.__path__[0])

EXPECTED_ROUTES: set[str] = {
    "/markets/preferences",
    "/markets/instruments",
    "/markets/refresh-metadata",
    "/markets/forex",
    "/markets/crypto",
    "/markets/commodities",
    "/markets/fuel",
    "/markets/ticker",
    "/markets/ingest",
}


def test_market_data_imports_clean() -> None:
    """Every surviving module under market_data imports without errors."""
    surviving_modules = [
        "app.modules.market_data.api",
        "app.modules.market_data.reader",
        "app.modules.market_data.facade",
        "app.modules.market_data.fetching",
        "app.modules.market_data.ticker",
        "app.modules.market_data.fuel",
        "app.modules.market_data.ingestion",
        "app.modules.market_data.dto",
        "app.modules.market_data.schemas",
        "app.modules.market_data.providers",
        "app.modules.market_data.providers.base",
        "app.modules.market_data.providers.binance_adapter",
        "app.modules.market_data.providers.commodities_adapter",
        "app.modules.market_data.providers.crypto_adapter",
        "app.modules.market_data.providers.forex_adapter",
        "app.modules.market_data.providers.fuel_adapter",
    ]
    for module_path in surviving_modules:
        importlib.import_module(module_path)


def test_market_data_routes_registered() -> None:
    """The /markets router still exposes the full live endpoint set."""
    actual_paths = {route.path for route in market_data_api.router.routes}
    missing = EXPECTED_ROUTES - actual_paths
    assert not missing, f"Missing endpoints on /markets router: {sorted(missing)}"


def test_no_provider_imports_service() -> None:
    """Regression guard: no provider adapter is allowed to import from market_data.service."""
    forbidden = re.compile(
        r"from\s+app\.modules\.market_data\.service\s+import|"
        r"import\s+app\.modules\.market_data\.service"
    )
    offenders: list[str] = []
    for path in PROVIDERS_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if forbidden.search(text):
            offenders.append(str(path.relative_to(PROVIDERS_DIR.parent)))
    assert offenders == [], (
        "Providers must not depend on market_data.service "
        f"(dependency inversion). Offenders: {offenders}"
    )


@pytest.mark.parametrize(
    "module_path, symbol",
    [
        ("app.modules.market_data.aggregation", "MarketDataAggregateService"),
        ("app.modules.market_data.models", "anything"),
        (
            "app.modules.market_data.providers.commodities_goldapi_alphavantage",
            "CommoditiesGoldAPIAlphaVantageAdapter",
        ),
        ("app.modules.market_data.service", "MarketDataService"),
        ("app.modules.market_data.tasks", "ingest_market_data"),
    ],
)
def test_removed_modules_gone(module_path: str, symbol: str) -> None:
    """Modules deleted in M1/M3a/M3b must no longer be importable."""
    _ = symbol
    with pytest.raises(ImportError):
        importlib.import_module(module_path)


@pytest.mark.parametrize(
    "module_path, attribute",
    [
        ("app.modules.market_data.ingestion", "MarketDataIngestionService"),
        ("app.modules.market_data.providers", "CommoditiesHttpAdapter"),
        ("app.modules.market_data.providers", "CommoditiesGoldAPIAlphaVantageAdapter"),
        ("app.modules.market_data.schemas", "ForexRateItem"),
        ("app.modules.market_data.schemas", "ForexResponse"),
        ("app.modules.market_data.schemas", "CryptoItem"),
        ("app.modules.market_data.schemas", "CryptoResponse"),
        ("app.modules.market_data.schemas", "CommodityItem"),
        ("app.modules.market_data.schemas", "CommoditiesResponse"),
        ("app.modules.market_data.schemas", "FuelPriceItem"),
        ("app.modules.market_data.schemas", "FuelResponse"),
        ("app.modules.market_data.schemas", "TickerItem"),
        ("app.modules.market_data.schemas", "TickerResponse"),
        ("app.modules.market_data.schemas", "RefreshMetadataResponse"),
        ("app.modules.market_data.fetching", "get_cache_info"),
    ],
)
def test_removed_symbols_gone(module_path: str, attribute: str) -> None:
    """Symbols removed in M1/M2/M3a must no longer resolve on their parent module."""
    module = importlib.import_module(module_path)
    assert not hasattr(module, attribute), (
        f"{module_path}.{attribute} should be removed"
    )


def test_providers_package_exports_no_removed_aliases() -> None:
    """Re-exports of removed adapters must be gone from providers.__all__."""
    removed = {"CommoditiesHttpAdapter", "CommoditiesGoldAPIAlphaVantageAdapter"}
    exported = set(getattr(providers_pkg, "__all__", []))
    leaked = exported & removed
    assert leaked == set(), f"providers.__all__ still re-exports removed names: {leaked}"


def test_no_stray_init_file() -> None:
    """The non-package 'init.py' must not exist; only '__init__.py' is allowed."""
    module_dir = Path(market_data_api.__file__).parent
    stray = module_dir / "init.py"
    assert not stray.exists(), f"Stray non-package file present: {stray}"


def test_providers_package_discovery_does_not_break() -> None:
    """Walking the providers package after M1 still yields the surviving adapters."""
    found = {name for _, name, _ in pkgutil.iter_modules(providers_pkg.__path__)}
    expected_subset = {
        "base",
        "binance_adapter",
        "commodities_adapter",
        "crypto_adapter",
        "forex_adapter",
        "fuel_adapter",
    }
    missing = expected_subset - found
    assert not missing, f"Provider modules missing after refactor: {missing}"
    assert "commodities_goldapi_alphavantage" not in found
