"""
M3a structure tests for the market_data module.

Verifies the post-split layout: service.py is retired, every former public
symbol lives in exactly one new file (reader / facade / fetching / ticker /
fuel), the api.py route set is unchanged, ticker assembly retains its
pre-split behaviour (including the known-dead live-fallback fuel branch),
and ingestion still reaches fetching.*.

After D1 the dashboard module no longer exists; the C3 analytics routes and
their facade stubs were removed together. The dissolution itself is covered
by test_d1_dashboard_dissolution.py.
"""

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.market_data import (
    api as market_api,
    facade as facade_mod,
    fetching as fetching_mod,
    fuel as fuel_mod,
    reader as reader_mod,
    ticker as ticker_mod,
)
from app.modules.market_data.facade import MarketsService
from app.modules.market_data.fetching import (
    fetch_commodities,
    fetch_crypto_prices,
    fetch_forex_rates,
)
from app.modules.market_data.fuel import get_fuel_prices
from app.modules.market_data.ingestion import IngestionService
from app.modules.market_data.reader import MarketDataService
from app.modules.market_data.ticker import get_ticker_data

EXPECTED_MARKETS_ROUTES: set[str] = {
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


def test_service_module_gone() -> None:
    """app.modules.market_data.service is retired in M3a."""
    with pytest.raises(ImportError):
        importlib.import_module("app.modules.market_data.service")


def test_symbols_relocated_to_new_homes() -> None:
    """Every former service.py public symbol lives at its new location."""
    assert reader_mod.MarketDataService is MarketDataService
    assert facade_mod.MarketsService is MarketsService
    assert fetching_mod.fetch_forex_rates is fetch_forex_rates
    assert fetching_mod.fetch_crypto_prices is fetch_crypto_prices
    assert fetching_mod.fetch_commodities is fetch_commodities
    assert ticker_mod.get_ticker_data is get_ticker_data
    assert fuel_mod.get_fuel_prices is get_fuel_prices


@pytest.mark.parametrize(
    "symbol, expected_module",
    [
        (MarketDataService, "app.modules.market_data.reader"),
        (MarketsService, "app.modules.market_data.facade"),
        (fetch_forex_rates, "app.modules.market_data.fetching"),
        (fetch_crypto_prices, "app.modules.market_data.fetching"),
        (fetch_commodities, "app.modules.market_data.fetching"),
        (get_ticker_data, "app.modules.market_data.ticker"),
        (get_fuel_prices, "app.modules.market_data.fuel"),
    ],
)
def test_each_symbol_defined_in_its_canonical_file(symbol, expected_module: str) -> None:
    """Every public symbol's source of truth lives in exactly one file (no duplicate definitions)."""
    assert symbol.__module__ == expected_module, (
        f"{symbol.__qualname__} is defined in {symbol.__module__}, expected {expected_module}"
    )


def test_routes_unchanged_markets() -> None:
    """/markets path set must match the post-M2 expectation."""
    actual_paths = {route.path for route in market_api.router.routes}
    missing = EXPECTED_MARKETS_ROUTES - actual_paths
    assert not missing, f"Missing /markets routes after restructure: {sorted(missing)}"
    assert actual_paths == EXPECTED_MARKETS_ROUTES, (
        f"Unexpected /markets routes: {sorted(actual_paths - EXPECTED_MARKETS_ROUTES)}"
    )


def test_currency_module_imports_from_fetching() -> None:
    """common.currency must reach fetch_forex_rates via the new fetching path."""
    from app.common import currency

    assert "from app.modules.market_data.fetching import fetch_forex_rates" in (
        importlib.import_module(currency.__name__).__loader__.get_source(currency.__name__) or ""
    )


@pytest.mark.asyncio
async def test_ticker_assembly_parity_no_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_ticker_data falls back to fetching.* and preserves the dead fuel branch."""

    async def empty_ticker(self, *args, **kwargs):
        _ = self, args, kwargs
        return []

    monkeypatch.setattr(
        "app.modules.market_data.reader.MarketDataService.get_ticker",
        empty_ticker,
    )
    monkeypatch.setattr(
        "app.modules.market_data.ticker.fetch_forex_rates",
        AsyncMock(
            return_value=[
                {"pair": "EUR/USD", "rate": 1.08, "change_24h": 0.1},
                {"pair": "EUR/GBP", "rate": 0.86, "change_24h": None},
            ]
        ),
    )
    monkeypatch.setattr(
        "app.modules.market_data.ticker.fetch_crypto_prices",
        AsyncMock(
            return_value=(
                [
                    {"symbol": "BTC", "price": 65000.0, "change_24h": 1.2},
                    {"symbol": "ETH", "price": 3500.0, "change_24h": None},
                ],
                False,
            )
        ),
    )
    monkeypatch.setattr(
        "app.modules.market_data.ticker.fetch_commodities",
        AsyncMock(
            return_value=(
                [
                    {"symbol": "XAU", "name": "Gold", "price": 2400.0, "unit": "oz", "change_24h": 0.5},
                ],
                None,
                False,
            )
        ),
    )

    fake_db = SimpleNamespace()
    items = await get_ticker_data(country_code="DE", db=fake_db)

    types = [row["type"] for row in items]
    assert "forex" in types
    assert "crypto" in types
    assert "commodity" in types
    assert "fuel" not in types, (
        "Dead live-fallback fuel branch must stay empty in M3a (parity-preserved)"
    )
    forex_rows = [row for row in items if row["type"] == "forex"]
    assert {row["label"] for row in forex_rows} == {"EUR/USD", "EUR/GBP"}
    crypto_rows = [row for row in items if row["type"] == "crypto"]
    assert {row["label"] for row in crypto_rows} == {"BTC", "ETH"}
    commodity_rows = [row for row in items if row["type"] == "commodity"]
    assert commodity_rows[0]["label"] == "Gold"
    assert commodity_rows[0]["suffix"] == "/oz"


@pytest.mark.asyncio
async def test_ingestion_uses_fetching_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """IngestionService.ingest_all reaches fetching.* (not the retired service.*)."""
    monkeypatch.setattr(
        "app.modules.market_data.fetching.fetch_forex_rates",
        AsyncMock(return_value=[{"pair": "EUR/USD", "rate": 1.08, "change_24h": None}]),
    )
    monkeypatch.setattr(
        "app.modules.market_data.fetching.fetch_crypto_prices",
        AsyncMock(
            return_value=(
                [
                    {
                        "symbol": "BTC",
                        "name": "BTC",
                        "price": 65000.0,
                        "change_24h": 1.0,
                        "market_cap": 1.3e12,
                        "volume_24h": None,
                        "image": "",
                    }
                ],
                False,
            )
        ),
    )
    monkeypatch.setattr(
        "app.modules.market_data.fetching.fetch_commodities",
        AsyncMock(
            return_value=(
                [{"symbol": "XAU", "name": "Gold", "price": 2400.0, "unit": "oz", "change_24h": 0.5}],
                None,
                False,
            )
        ),
    )

    fake_db = SimpleNamespace(commit=AsyncMock())
    service = IngestionService(fake_db)
    service.persist_forex = AsyncMock(return_value=1)
    service.persist_crypto = AsyncMock(return_value=1)
    service.persist_commodities = AsyncMock(return_value=1)

    result = await service.ingest_all(include_commodities=True)

    assert service.persist_forex.await_count == 1
    assert service.persist_crypto.await_count == 1
    assert service.persist_commodities.await_count == 1
    assert result == {"forex": 1, "crypto": 1, "commodities": 1}
