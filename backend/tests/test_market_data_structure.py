"""
M3a structure tests for the market_data module.

Verifies the post-split layout: service.py is retired, every former public
symbol lives in exactly one new file (reader / facade / fetching / ticker),
the api.py route set, ticker live-fallback mirrors the DB path
(exactly-saved favorites, derive_forex_pairs), and ingestion still reaches
fetching.*.

After TICKER-FIX-B the live-fallback branch mirrors reader.get_ticker parity
(exactly-saved favorites, no slice caps, forex via derive_forex_pairs).
"""

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.market_data import (
    api as market_api,
)
from app.modules.market_data import (
    facade as facade_mod,
)
from app.modules.market_data import (
    fetching as fetching_mod,
)
from app.modules.market_data import (
    reader as reader_mod,
)
from app.modules.market_data import (
    ticker as ticker_mod,
)
from app.modules.market_data.facade import MarketsService
from app.modules.market_data.fetching import (
    fetch_commodities,
    fetch_crypto_prices,
    fetch_forex_rates,
)
from app.modules.market_data.ingestion import IngestionService
from app.modules.market_data.reader import MarketDataService
from app.modules.market_data.ticker import get_ticker_data

EXPECTED_MARKETS_ROUTES: set[str] = {
    "/markets/preferences",
    "/markets/instruments",
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


@pytest.mark.parametrize(
    "symbol, expected_module",
    [
        (MarketDataService, "app.modules.market_data.reader"),
        (MarketsService, "app.modules.market_data.facade"),
        (fetch_forex_rates, "app.modules.market_data.fetching"),
        (fetch_crypto_prices, "app.modules.market_data.fetching"),
        (fetch_commodities, "app.modules.market_data.fetching"),
        (get_ticker_data, "app.modules.market_data.ticker"),
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


def test_currency_module_imports_from_forex_fetch() -> None:
    """display_converter live path must use currency.forex_fetch, not market_data directly."""
    from app.modules.currency import display_converter

    source = importlib.import_module(display_converter.__name__).__loader__.get_source(
        display_converter.__name__,
    ) or ""
    assert "from app.modules.currency.forex_fetch import fetch_eur_base_pairs" in source
    assert "from app.modules.market_data.fetching import fetch_forex_rates" not in source


@pytest.mark.asyncio
async def test_ticker_fallback_empty_favorites(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live fallback emits nothing when all favorite sets are empty (DB parity)."""

    async def empty_ticker(self, *args, **kwargs):
        _ = self, args, kwargs
        return []

    fetch_forex = AsyncMock()
    fetch_crypto = AsyncMock()
    fetch_commodity = AsyncMock()
    monkeypatch.setattr("app.modules.market_data.reader.MarketDataService.get_ticker", empty_ticker)
    monkeypatch.setattr("app.modules.market_data.ticker.fetch_forex_rates", fetch_forex)
    monkeypatch.setattr("app.modules.market_data.ticker.fetch_crypto_prices", fetch_crypto)
    monkeypatch.setattr("app.modules.market_data.ticker.fetch_commodities", fetch_commodity)

    items = await get_ticker_data(country_code="DE", db=SimpleNamespace())

    assert items == []
    fetch_forex.assert_not_called()
    fetch_crypto.assert_not_called()
    fetch_commodity.assert_not_called()


@pytest.mark.asyncio
async def test_ticker_fallback_forex_derive_exact_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live fallback derives forex pairs and filters to exactly-saved favorites."""

    async def empty_ticker(self, *args, **kwargs):
        _ = self, args, kwargs
        return []

    monkeypatch.setattr("app.modules.market_data.reader.MarketDataService.get_ticker", empty_ticker)
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
        AsyncMock(return_value=([], False)),
    )
    monkeypatch.setattr(
        "app.modules.market_data.ticker.fetch_commodities",
        AsyncMock(return_value=([], None, False)),
    )

    items = await get_ticker_data(
        country_code="DE",
        db=SimpleNamespace(),
        forex_favorites=["EUR/USD", "USD/EUR", "GBP/USD"],
    )

    forex_rows = {row["label"]: row for row in items if row["type"] == "forex"}
    assert set(forex_rows) == {"EUR/USD", "USD/EUR", "GBP/USD"}
    assert forex_rows["EUR/USD"]["value"] == pytest.approx(1.08, rel=1e-4)
    assert forex_rows["USD/EUR"]["value"] == pytest.approx(1.0 / 1.08, rel=1e-4)
    assert forex_rows["GBP/USD"]["value"] == pytest.approx(1.08 / 0.86, rel=1e-4)
    assert all(row["change"] is None for row in forex_rows.values())


@pytest.mark.asyncio
async def test_ticker_fallback_crypto_commodity_no_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live fallback filters crypto/commodities to saved symbols without slice caps."""

    async def empty_ticker(self, *args, **kwargs):
        _ = self, args, kwargs
        return []

    monkeypatch.setattr("app.modules.market_data.reader.MarketDataService.get_ticker", empty_ticker)
    monkeypatch.setattr(
        "app.modules.market_data.ticker.fetch_forex_rates",
        AsyncMock(return_value=[]),
    )
    many_coins = [
        {"symbol": sym, "price": float(idx), "change_24h": None}
        for idx, sym in enumerate(["BTC", "ETH", "SOL", "ADA", "DOT", "XRP"], start=1)
    ]
    monkeypatch.setattr(
        "app.modules.market_data.ticker.fetch_crypto_prices",
        AsyncMock(return_value=(many_coins, False)),
    )
    commodity_fixtures = [
        {
            "symbol": "XAU",
            "name": "Gold",
            "price": 2400.0,
            "unit": "oz",
            "change_24h": 0.5,
        },
        {
            "symbol": "XAG",
            "name": "Silver",
            "price": 28.0,
            "unit": "oz",
            "change_24h": None,
        },
    ]
    monkeypatch.setattr(
        "app.modules.market_data.ticker.fetch_commodities",
        AsyncMock(return_value=(commodity_fixtures, None, False)),
    )

    items = await get_ticker_data(
        country_code="DE",
        db=SimpleNamespace(),
        crypto_favorites=["BTC", "SOL"],
        commodity_favorites=["XAU"],
    )

    assert "fuel" not in {row["type"] for row in items}
    crypto_rows = [row for row in items if row["type"] == "crypto"]
    assert {row["label"] for row in crypto_rows} == {"BTC", "SOL"}
    commodity_rows = [row for row in items if row["type"] == "commodity"]
    assert len(commodity_rows) == 1
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

    fake_db = SimpleNamespace(commit=MagicMock())
    service = IngestionService(fake_db)
    service.persist_forex = MagicMock(return_value=1)
    service.persist_crypto = MagicMock(return_value=1)
    service.persist_commodities = MagicMock(return_value=1)

    result = await service.ingest_all(include_commodities=True)

    assert service.persist_forex.call_count == 1
    assert service.persist_crypto.call_count == 1
    assert service.persist_commodities.call_count == 1
    assert result == {"forex": 1, "crypto": 1, "commodities": 1}
