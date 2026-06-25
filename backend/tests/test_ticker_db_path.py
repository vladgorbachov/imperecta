"""DB-path ticker assembly tests for MarketDataService.get_ticker."""

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
async def test_get_ticker_single_favorite_no_auto_inverse(
    market_data_service: MarketDataService,
) -> None:
    """Saved EUR/TRY only — TRY/EUR must not appear unless explicitly saved."""
    items = await market_data_service.get_ticker(
        "DE",
        forex_favorites=["EUR/TRY"],
        crypto_favorites=[],
        commodity_favorites=[],
    )
    forex_symbols = {row["symbol"] for row in items if row["type"] == "forex"}
    assert forex_symbols == {"EUR/TRY"}
    assert "TRY/EUR" not in forex_symbols


@pytest.mark.asyncio
async def test_get_ticker_both_directions_only_when_both_saved(
    market_data_service: MarketDataService,
) -> None:
    """EUR/MDL and MDL/EUR both saved — both appear; no extra pairs."""
    items = await market_data_service.get_ticker(
        "DE",
        forex_favorites=["EUR/MDL", "MDL/EUR"],
        crypto_favorites=[],
        commodity_favorites=[],
    )
    forex_symbols = {row["symbol"] for row in items if row["type"] == "forex"}
    assert forex_symbols == {"EUR/MDL", "MDL/EUR"}


@pytest.mark.asyncio
async def test_get_ticker_saved_subset_matches_exactly(
    market_data_service: MarketDataService,
) -> None:
    """Seven prod-like favorites yield seven forex rows — no auto-added inverses."""
    saved = [
        "EUR/MDL",
        "EUR/RON",
        "EUR/TRY",
        "EUR/USD",
        "MDL/EUR",
        "USD/EUR",
        "USD/MDL",
    ]
    items = await market_data_service.get_ticker(
        "DE",
        forex_favorites=saved,
        crypto_favorites=[],
        commodity_favorites=[],
    )
    forex_symbols = {row["symbol"] for row in items if row["type"] == "forex"}
    assert forex_symbols == set(saved)
    assert "TRY/EUR" not in forex_symbols
    assert "RON/EUR" not in forex_symbols
    assert "MDL/USD" not in forex_symbols


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
