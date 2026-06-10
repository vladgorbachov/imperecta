"""
M2 consolidation tests for the market_data module.

Verifies that all external HTTP fetch lives in providers/, that the module-level
fetch_* helpers are thin provider wrappers, and that the global in-memory cache
has been removed without breaking the public signatures used by api.py and
ingestion.py.
"""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.market_data import service as market_service
from app.modules.market_data.dto import (
    NormalizedCommodity,
    NormalizedCrypto,
    NormalizedForex,
)
from app.modules.market_data.ingestion import IngestionService

SERVICE_PATH = Path(market_service.__file__)


def _ts() -> datetime:
    return datetime(2026, 6, 9, tzinfo=timezone.utc)


def _forex_dtos() -> list[NormalizedForex]:
    return [
        NormalizedForex(
            symbol="EUR/USD",
            bid=Decimal("1.080000"),
            ask=Decimal("1.081000"),
            spread=Decimal("0.001"),
            change_24h=0.12,
            refreshed_at=_ts(),
        ),
        NormalizedForex(
            symbol="EUR/GBP",
            bid=Decimal("0.860000"),
            ask=Decimal("0.861000"),
            spread=Decimal("0.001"),
            change_24h=None,
            refreshed_at=_ts(),
        ),
        NormalizedForex(
            symbol="USD/JPY",
            bid=Decimal("150.00"),
            ask=Decimal("150.01"),
            spread=Decimal("0.01"),
            change_24h=None,
            refreshed_at=_ts(),
        ),
    ]


def _crypto_dtos() -> list[NormalizedCrypto]:
    return [
        NormalizedCrypto(
            symbol="BTC",
            price=Decimal("65000.5"),
            change_24h=1.234,
            market_cap=Decimal("1300000000000"),
            refreshed_at=_ts(),
        ),
        NormalizedCrypto(
            symbol="ETH",
            price=Decimal("3500.0"),
            change_24h=None,
            market_cap=None,
            refreshed_at=_ts(),
        ),
    ]


def _commodity_dtos() -> list[NormalizedCommodity]:
    return [
        NormalizedCommodity(
            symbol="XAU",
            name="Gold",
            price=Decimal("2400.5"),
            change_24h=0.5,
            unit="oz",
            refreshed_at=_ts(),
        ),
        NormalizedCommodity(
            symbol="WTI",
            name="Crude Oil (WTI)",
            price=Decimal("75.30"),
            change_24h=None,
            unit="bbl",
            refreshed_at=_ts(),
        ),
    ]


@pytest.mark.asyncio
async def test_fetch_forex_uses_provider_no_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_forex_rates delegates to ForexUnifiedAdapter on every call (no cache)."""
    fetch_mock = AsyncMock(return_value=_forex_dtos())
    monkeypatch.setattr(
        "app.modules.market_data.providers.forex_adapter.ForexUnifiedAdapter.fetch",
        fetch_mock,
    )

    first = await market_service.fetch_forex_rates("EUR")
    second = await market_service.fetch_forex_rates("EUR")

    assert fetch_mock.await_count == 2, "Adapter must be called every time (cache removed)"
    assert first == second
    pairs = [row["pair"] for row in first]
    assert pairs == sorted(pairs), "Pairs must be sorted ascending"
    assert all(row["pair"].startswith("EUR/") for row in first)
    sample = first[0]
    assert set(sample.keys()) == {"pair", "rate", "change_24h"}


@pytest.mark.asyncio
async def test_fetch_forex_returns_empty_on_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider failure yields an empty list (no stale fallback after cache removal)."""
    fetch_mock = AsyncMock(side_effect=RuntimeError("upstream down"))
    monkeypatch.setattr(
        "app.modules.market_data.providers.forex_adapter.ForexUnifiedAdapter.fetch",
        fetch_mock,
    )
    result = await market_service.fetch_forex_rates("EUR")
    assert result == []


@pytest.mark.asyncio
async def test_fetch_crypto_second_bool_always_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_crypto_prices returns (items, False) always; cache removed in M2."""
    fetch_mock = AsyncMock(return_value=_crypto_dtos())
    monkeypatch.setattr(
        "app.modules.market_data.providers.crypto_adapter.CryptoUnifiedAdapter.fetch",
        fetch_mock,
    )

    items_one, from_cache_one = await market_service.fetch_crypto_prices()
    items_two, from_cache_two = await market_service.fetch_crypto_prices()

    assert fetch_mock.await_count == 2
    assert from_cache_one is False
    assert from_cache_two is False
    assert [row["symbol"] for row in items_one] == ["BTC", "ETH"]
    assert items_one[0]["price"] == 65000.5
    assert items_one[0]["change_24h"] == 1.23
    assert items_two == items_one


@pytest.mark.asyncio
async def test_fetch_commodities_uses_unified_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_commodities returns (items, None, False); always-fresh, never cached."""
    fetch_mock = AsyncMock(return_value=_commodity_dtos())
    monkeypatch.setattr(
        "app.modules.market_data.providers.commodities_adapter.CommoditiesUnifiedAdapter.fetch",
        fetch_mock,
    )

    items, error, from_cache = await market_service.fetch_commodities()
    assert error is None
    assert from_cache is False
    symbols = [row["symbol"] for row in items]
    assert symbols == ["XAU", "WTI"]
    assert items[0]["name"] == "Gold"
    assert items[0]["unit"] == "oz"


@pytest.mark.asyncio
async def test_fetch_commodities_provider_failure_returns_error_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider exception is reported as ([], error_msg, False), preserving tuple shape."""
    monkeypatch.setattr(
        "app.modules.market_data.providers.commodities_adapter.CommoditiesUnifiedAdapter.fetch",
        AsyncMock(side_effect=RuntimeError("gold api down")),
    )
    items, error, from_cache = await market_service.fetch_commodities()
    assert items == []
    assert error is not None
    assert from_cache is False


def test_no_http_in_service() -> None:
    """All external HTTP must live in providers/; service.py must not use httpx."""
    text = SERVICE_PATH.read_text(encoding="utf-8")
    assert "import httpx" not in text
    assert "from httpx" not in text
    assert "httpx.AsyncClient" not in text


@pytest.mark.parametrize(
    "symbol",
    ["_cache", "_get_cached", "_set_cached", "DEFAULT_TTL"],
)
def test_cache_symbols_removed(symbol: str) -> None:
    """The module-global in-memory cache must be gone after M2."""
    assert not hasattr(market_service, symbol), (
        f"market_data.service.{symbol} must be removed in M2"
    )


@pytest.mark.parametrize(
    "symbol",
    [
        "fetch_metals",
        "fetch_energy",
        "_fetch_one_metal",
        "_fetch_alpha_vantage",
        "GOLDAPI_METALS",
        "ALPHA_VANTAGE_TICKERS",
        "ALPHA_VANTAGE_FUNCTIONS",
        "GOLDAPI_TTL",
        "ALPHA_VANTAGE_TTL",
    ],
)
def test_metals_energy_removed(symbol: str) -> None:
    """The orphaned metals/energy duplicate path is removed from service.py."""
    assert not hasattr(market_service, symbol), (
        f"market_data.service.{symbol} must be removed in M2"
    )


def test_public_fetch_signatures_preserved() -> None:
    """The three public fetch_* helpers must remain importable with the same name."""
    from app.modules.market_data.service import (  # noqa: F401
        fetch_commodities,
        fetch_crypto_prices,
        fetch_forex_rates,
    )


@pytest.mark.asyncio
async def test_ingestion_persists_all_three_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    """IngestionService.ingest_all still routes mapped items into persist_* (parity)."""
    monkeypatch.setattr(
        "app.modules.market_data.service.fetch_forex_rates",
        AsyncMock(
            return_value=[
                {"pair": "EUR/USD", "rate": 1.08, "change_24h": None},
                {"pair": "EUR/GBP", "rate": 0.86, "change_24h": None},
            ]
        ),
    )
    monkeypatch.setattr(
        "app.modules.market_data.service.fetch_crypto_prices",
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
        "app.modules.market_data.service.fetch_commodities",
        AsyncMock(
            return_value=(
                [
                    {
                        "symbol": "XAU",
                        "name": "Gold",
                        "price": 2400.0,
                        "unit": "oz",
                        "change_24h": 0.5,
                    }
                ],
                None,
                False,
            )
        ),
    )

    fake_db = SimpleNamespace(commit=AsyncMock())
    service = IngestionService(fake_db)
    persist_forex = AsyncMock(return_value=2)
    persist_crypto = AsyncMock(return_value=1)
    persist_commodities = AsyncMock(return_value=1)
    service.persist_forex = persist_forex
    service.persist_crypto = persist_crypto
    service.persist_commodities = persist_commodities

    result = await service.ingest_all(include_commodities=True)

    assert persist_forex.await_count == 1
    assert persist_crypto.await_count == 1
    assert persist_commodities.await_count == 1

    forex_items = persist_forex.await_args.args[0]
    currencies = {item.currency_code for item in forex_items}
    assert currencies == {"USD", "GBP"}

    crypto_items = persist_crypto.await_args.args[0]
    assert crypto_items[0].symbol == "BTC"
    assert crypto_items[0].rank == 1

    commodity_items = persist_commodities.await_args.args[0]
    assert commodity_items[0].symbol == "XAU"
    assert commodity_items[0].commodity_type == "metal"

    assert result == {"forex": 2, "crypto": 1, "commodities": 1}
