"""DB-path ticker assembly tests for MarketDataService.get_ticker (TICKER-FIX-A)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.market_data.reader import MarketDataService

_SAMPLE_FOREX_ROWS = [
    {"currency_code": "USD", "rate_to_eur": 0.92},
    {"currency_code": "GBP", "rate_to_eur": 0.78},
    {"currency_code": "JPY", "rate_to_eur": 0.0062},
    {"currency_code": "CHF", "rate_to_eur": 1.05},
    {"currency_code": "MDL", "rate_to_eur": 0.051},
    {"currency_code": "RON", "rate_to_eur": 0.20},
    {"currency_code": "PLN", "rate_to_eur": 0.23},
    {"currency_code": "TRY", "rate_to_eur": 0.027},
]


def _crypto_row(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "name": symbol,
        "price_usd": 1.0,
        "change_24h_pct": 0.1,
    }


@pytest.fixture
def market_data_service(monkeypatch: pytest.MonkeyPatch) -> MarketDataService:
    """MarketDataService with mocked fact reads (no DB session required)."""
    service = MarketDataService(SimpleNamespace())

    async def get_forex(self) -> list[dict]:
        return _SAMPLE_FOREX_ROWS

    async def get_crypto(self) -> list[dict]:
        return [_crypto_row(f"C{i}") for i in range(1, 8)]

    async def get_commodities(self) -> list[dict]:
        return [
            {
                "symbol": "XAU",
                "name": "Gold",
                "price_usd": 2400.0,
                "change_24h_pct": 0.5,
                "unit": "oz",
            }
        ]

    async def get_fuel_should_not_run(self, country_code: str) -> list[dict]:
        raise AssertionError("get_fuel must not be called from get_ticker")

    monkeypatch.setattr(MarketDataService, "get_forex", get_forex)
    monkeypatch.setattr(MarketDataService, "get_crypto", get_crypto)
    monkeypatch.setattr(MarketDataService, "get_commodities", get_commodities)
    monkeypatch.setattr(MarketDataService, "get_fuel", get_fuel_should_not_run)
    return service


@pytest.mark.asyncio
async def test_get_ticker_auto_inverse_from_single_favorite(
    market_data_service: MarketDataService,
) -> None:
    """Stored EUR/USD yields both EUR/USD and USD/EUR rows from derive_forex_pairs."""
    items = await market_data_service.get_ticker(
        "DE",
        forex_favorites=["EUR/USD"],
        crypto_favorites=[],
        commodity_favorites=[],
    )
    forex_symbols = {row["symbol"] for row in items if row["type"] == "forex"}
    assert forex_symbols == {"EUR/USD", "USD/EUR"}


@pytest.mark.asyncio
async def test_get_ticker_empty_forex_favorites_yields_no_forex(
    market_data_service: MarketDataService,
) -> None:
    items = await market_data_service.get_ticker(
        "DE",
        forex_favorites=[],
        crypto_favorites=["C1"],
        commodity_favorites=[],
    )
    assert not any(row["type"] == "forex" for row in items)
    assert {row["symbol"] for row in items if row["type"] == "crypto"} == {"C1"}


@pytest.mark.asyncio
async def test_get_ticker_crypto_no_five_cap(
    market_data_service: MarketDataService,
) -> None:
    favorites = [f"C{i}" for i in range(1, 8)]
    items = await market_data_service.get_ticker(
        "DE",
        forex_favorites=[],
        crypto_favorites=favorites,
        commodity_favorites=[],
    )
    crypto_symbols = {row["symbol"] for row in items if row["type"] == "crypto"}
    assert crypto_symbols == set(favorites)


@pytest.mark.asyncio
async def test_get_ticker_empty_crypto_and_commodity_skipped(
    market_data_service: MarketDataService,
) -> None:
    items = await market_data_service.get_ticker(
        "DE",
        forex_favorites=["EUR/USD"],
        crypto_favorites=[],
        commodity_favorites=[],
    )
    types = {row["type"] for row in items}
    assert "crypto" not in types
    assert "commodity" not in types
    assert "fuel" not in types


@pytest.mark.asyncio
async def test_get_ticker_no_fuel_rows(market_data_service: MarketDataService) -> None:
    items = await market_data_service.get_ticker(
        "DE",
        forex_favorites=["EUR/USD"],
        crypto_favorites=["C1"],
        commodity_favorites=["XAU"],
    )
    assert not any(row["type"] == "fuel" for row in items)
