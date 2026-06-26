"""DB-free tests for cross-provider Q-B gap-fill queue and forex seam 1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.currency.display_converter import CurrencyConverter
from app.modules.market_data.dto import NormalizedCommodity, NormalizedCrypto, NormalizedForex
from app.modules.market_data.ingestion import CryptoIngestItem, ForexIngestItem, IngestionService
from app.modules.market_data.provider_queue import gap_fill_fetch


@dataclass
class _StubProvider:
    """Minimal InstrumentProvider for queue unit tests."""

    source: str
    mapping: dict[str, str]
    calls: list[frozenset[str]] = field(default_factory=list)

    @property
    def provider_source(self) -> str:
        return self.source

    async def fetch_instruments(self, requested: frozenset[str]) -> dict[str, str]:
        self.calls.append(requested)
        return {key: self.mapping[key] for key in requested if key in self.mapping}


@pytest.mark.asyncio
async def test_gap_fill_provider_b_fills_missing_only() -> None:
    """Provider A returns a subset; provider B receives only still-missing keys."""
    provider_a = _StubProvider("alpha", {"USD": "usd-a"})
    provider_b = _StubProvider("beta", {"GBP": "gbp-b", "USD": "usd-b"})

    result = await gap_fill_fetch(
        [provider_a, provider_b],
        frozenset({"USD", "GBP"}),
    )

    assert provider_a.calls == [frozenset({"USD", "GBP"})]
    assert provider_b.calls == [frozenset({"GBP"})]
    assert result.items == {
        "USD": ("usd-a", "alpha"),
        "GBP": ("gbp-b", "beta"),
    }
    assert result.missing == frozenset()


@pytest.mark.asyncio
async def test_gap_fill_honest_absence_when_no_provider_returns_key() -> None:
    """Keys no provider supplies stay missing (no fabricated values)."""
    provider_a = _StubProvider("alpha", {})
    provider_b = _StubProvider("beta", {"USD": "usd-b"})

    result = await gap_fill_fetch(
        [provider_a, provider_b],
        frozenset({"USD", "JPY"}),
    )

    assert result.items == {"USD": ("usd-b", "beta")}
    assert result.missing == frozenset({"JPY"})


@pytest.mark.asyncio
async def test_gap_fill_skips_later_providers_when_first_fills_all() -> None:
    """When provider A returns every requested key, provider B is not called."""
    provider_a = _StubProvider("alpha", {"USD": "usd-a", "GBP": "gbp-a"})
    provider_b = _StubProvider("beta", {"USD": "usd-b"})

    result = await gap_fill_fetch(
        [provider_a, provider_b],
        frozenset({"USD", "GBP"}),
    )

    assert provider_a.calls == [frozenset({"USD", "GBP"})]
    assert provider_b.calls == []
    assert set(result.items) == {"USD", "GBP"}
    assert all(source == "alpha" for _, source in result.items.values())


@pytest.mark.asyncio
async def test_fetch_forex_rates_carries_provider_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_forex_rates exposes provider_source from normalized DTOs."""
    refreshed = datetime(2026, 6, 9, tzinfo=timezone.utc)
    dtos = [
        NormalizedForex(
            symbol="EUR/USD",
            bid=Decimal("1.08"),
            ask=Decimal("1.0801"),
            spread=Decimal("0.0001"),
            change_24h=None,
            refreshed_at=refreshed,
            provider_source="openexchangerates",
        ),
    ]
    monkeypatch.setattr(
        "app.modules.market_data.providers.forex_adapter.ForexUnifiedAdapter.fetch",
        AsyncMock(return_value=dtos),
    )
    monkeypatch.setattr(
        "app.modules.market_data.fetching.load_market_data_http_config",
        lambda: SimpleNamespace(timeout_seconds=15.0, retry_attempts=0),
    )

    from app.modules.market_data.fetching import fetch_forex_rates

    rows = await fetch_forex_rates("EUR")
    assert rows[0]["provider_source"] == "openexchangerates"


@pytest.mark.asyncio
async def test_forex_ingest_item_source_not_custom(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forex ingest maps real provider_source instead of hardcoded custom."""
    monkeypatch.setattr(
        "app.modules.market_data.fetching.fetch_forex_rates",
        AsyncMock(
            return_value=[
                {
                    "pair": "EUR/USD",
                    "rate": 1.08,
                    "change_24h": None,
                    "provider_source": "ecb",
                },
            ],
        ),
    )
    monkeypatch.setattr(
        "app.modules.market_data.ingestion.Settings",
        lambda: SimpleNamespace(forex_allowed_currency_set={"EUR", "USD"}),
    )

    service = IngestionService(MagicMock())
    service.persist_forex = MagicMock(return_value=1)

    await service.ingest_all(include_commodities=False)

    items = service.persist_forex.call_args.args[0]
    assert len(items) == 1
    assert isinstance(items[0], ForexIngestItem)
    assert items[0].source == "ecb"
    assert items[0].source != "custom"


@pytest.mark.asyncio
async def test_display_converter_live_path_uses_currency_forex_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Display converter reaches forex via currency.forex_fetch (no common.currency)."""
    fetch_mock = AsyncMock(
        return_value=[{"pair": "EUR/USD", "rate": 1.08, "change_24h": None}],
    )
    monkeypatch.setattr(
        "app.modules.currency.forex_fetch.fetch_eur_base_pairs",
        fetch_mock,
    )

    rates = await CurrencyConverter._load_from_live()
    fetch_mock.assert_awaited_once()
    assert "USD" in rates
    assert rates["USD"].to_eur == pytest.approx(1.0 / 1.08)


def _crypto_dto(symbol: str, *, source: str, price: str = "100") -> NormalizedCrypto:
    return NormalizedCrypto(
        symbol=symbol,
        price=Decimal(price),
        change_24h=1.0,
        market_cap=Decimal("1000000"),
        refreshed_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
        provider_source=source,
    )


@pytest.mark.asyncio
async def test_crypto_queue_coingecko_fills_missing_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Binance returns a subset; CoinGecko gap-fills missing requested symbols."""
    binance_fetch = AsyncMock(
        return_value=[_crypto_dto("BTC", source="binance")],
    )
    coingecko_fetch = AsyncMock(
        return_value=[_crypto_dto("ETH", source="coingecko")],
    )
    monkeypatch.setattr(
        "app.modules.market_data.providers.binance_adapter.BinanceCryptoAdapter.fetch",
        binance_fetch,
    )
    monkeypatch.setattr(
        "app.modules.market_data.providers.crypto_adapter.CryptoCoingeckoAdapter.fetch",
        coingecko_fetch,
    )
    monkeypatch.setattr(
        "app.modules.market_data.providers.crypto_adapter.Settings",
        lambda: SimpleNamespace(market_data_crypto_url=""),
    )

    from app.modules.market_data.providers.crypto_adapter import fetch_crypto_normalized

    result = await fetch_crypto_normalized(
        retry_attempts=0,
        requested_symbols=frozenset({"BTC", "ETH"}),
    )

    assert binance_fetch.await_count == 1
    assert coingecko_fetch.await_count == 1
    by_symbol = {dto.symbol: dto.provider_source for dto in result}
    assert by_symbol == {"BTC": "binance", "ETH": "coingecko"}


@pytest.mark.asyncio
async def test_crypto_queue_skips_backup_when_primary_fills_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Binance returns every requested symbol, CoinGecko is not called."""
    binance_fetch = AsyncMock(
        return_value=[
            _crypto_dto("BTC", source="binance"),
            _crypto_dto("ETH", source="binance"),
        ],
    )
    coingecko_fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.modules.market_data.providers.binance_adapter.BinanceCryptoAdapter.fetch",
        binance_fetch,
    )
    monkeypatch.setattr(
        "app.modules.market_data.providers.crypto_adapter.CryptoCoingeckoAdapter.fetch",
        coingecko_fetch,
    )
    monkeypatch.setattr(
        "app.modules.market_data.providers.crypto_adapter.Settings",
        lambda: SimpleNamespace(market_data_crypto_url=""),
    )

    from app.modules.market_data.providers.crypto_adapter import fetch_crypto_normalized

    result = await fetch_crypto_normalized(
        retry_attempts=0,
        requested_symbols=frozenset({"BTC", "ETH"}),
    )

    assert coingecko_fetch.await_count == 0
    assert len(result) == 2
    assert all(dto.provider_source == "binance" for dto in result)


@pytest.mark.asyncio
async def test_crypto_queue_honest_absence_for_unsupplied_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Symbols no provider returns stay absent (no fabricated prices)."""
    monkeypatch.setattr(
        "app.modules.market_data.providers.binance_adapter.BinanceCryptoAdapter.fetch",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.modules.market_data.providers.crypto_adapter.CryptoCoingeckoAdapter.fetch",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.modules.market_data.providers.crypto_adapter.Settings",
        lambda: SimpleNamespace(market_data_crypto_url=""),
    )

    from app.modules.market_data.providers.crypto_adapter import fetch_crypto_normalized

    result = await fetch_crypto_normalized(
        retry_attempts=0,
        requested_symbols=frozenset({"DOGE"}),
    )

    assert result == []


@pytest.mark.asyncio
async def test_crypto_ingest_item_source_not_custom(monkeypatch: pytest.MonkeyPatch) -> None:
    """Crypto ingest maps real provider_source instead of hardcoded custom."""
    monkeypatch.setattr(
        "app.modules.market_data.fetching.fetch_forex_rates",
        AsyncMock(return_value=[]),
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
                        "provider_source": "coingecko",
                    },
                ],
                False,
            ),
        ),
    )
    monkeypatch.setattr(
        "app.modules.market_data.ingestion.Settings",
        lambda: SimpleNamespace(forex_allowed_currency_set={"EUR"}),
    )

    service = IngestionService(MagicMock())
    service.persist_crypto = MagicMock(return_value=1)

    await service.ingest_all(include_commodities=False)

    items = service.persist_crypto.call_args.args[0]
    assert len(items) == 1
    assert isinstance(items[0], CryptoIngestItem)
    assert items[0].source == "coingecko"
    assert items[0].source != "custom"


def test_crypto_queue_provider_order_binance_first() -> None:
    """Binance must be first so discovery uses volume-ranked universe."""
    from app.modules.market_data.providers.crypto_adapter import (
        CRYPTO_PROVIDER_BINANCE,
        CRYPTO_PROVIDER_COINGECKO,
        build_crypto_queue_providers,
    )

    providers = build_crypto_queue_providers(timeout=15.0, retry_attempts=0)
    assert len(providers) == 2
    assert providers[0].provider_source == CRYPTO_PROVIDER_BINANCE
    assert providers[1].provider_source == CRYPTO_PROVIDER_COINGECKO


@pytest.mark.asyncio
async def test_crypto_discovery_binance_defines_universe_not_configured_coingecko(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured CoinGecko URL must not run before Binance during universe discovery."""
    call_order: list[str] = []

    async def _binance_fetch(self) -> list[NormalizedCrypto]:
        call_order.append("binance")
        return [_crypto_dto("BTC", source="binance"), _crypto_dto("ETH", source="binance")]

    async def _coingecko_fetch(self) -> list[NormalizedCrypto]:
        call_order.append("coingecko")
        return [_crypto_dto("SOL", source="coingecko")]

    monkeypatch.setattr(
        "app.modules.market_data.providers.binance_adapter.BinanceCryptoAdapter.fetch",
        _binance_fetch,
    )
    monkeypatch.setattr(
        "app.modules.market_data.providers.crypto_adapter.CryptoCoingeckoAdapter.fetch",
        _coingecko_fetch,
    )
    monkeypatch.setattr(
        "app.modules.market_data.providers.crypto_adapter.Settings",
        lambda: SimpleNamespace(
            market_data_crypto_url="https://custom.coingecko.example/api/v3/coins/markets",
        ),
    )

    from app.modules.market_data.providers.crypto_adapter import fetch_crypto_normalized

    result = await fetch_crypto_normalized(retry_attempts=0)

    assert call_order[0] == "binance"
    assert "coingecko" not in call_order
    assert {dto.symbol for dto in result} == {"BTC", "ETH"}
    assert all(dto.provider_source == "binance" for dto in result)


def _commodity_dto(symbol: str, *, source: str) -> NormalizedCommodity:
    from app.modules.market_data.providers.commodities_adapter import _COMMODITY_CATALOG

    meta = _COMMODITY_CATALOG[symbol]
    return NormalizedCommodity(
        symbol=symbol,
        name=str(meta["name"]),
        price=Decimal("100"),
        change_24h=0.5,
        unit=str(meta["unit"]),
        refreshed_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
        provider_source=source,
    )


@pytest.mark.asyncio
async def test_commodities_queue_gap_fill_across_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gold API metals + Alpha Vantage energy; Yahoo fills remaining catalog gaps."""
    call_order: list[str] = []

    async def _gold_fetch(self, requested: frozenset[str]) -> dict[str, NormalizedCommodity]:
        call_order.append("goldapi")
        return {
            symbol: _commodity_dto(symbol, source="goldapi")
            for symbol in requested
            if symbol == "XAU"
        }

    async def _alpha_fetch(self, requested: frozenset[str]) -> dict[str, NormalizedCommodity]:
        call_order.append("alpha_vantage")
        return {
            symbol: _commodity_dto(symbol, source="alpha_vantage")
            for symbol in requested
            if symbol == "WTI"
        }

    async def _yahoo_fetch(self, requested: frozenset[str]) -> dict[str, NormalizedCommodity]:
        call_order.append("yahoo")
        return {
            symbol: _commodity_dto(symbol, source="yahoo")
            for symbol in requested
            if symbol == "XPD"
        }

    monkeypatch.setattr(
        "app.modules.market_data.providers.commodities_adapter._QueuedGoldApiProvider.fetch_instruments",
        _gold_fetch,
    )
    monkeypatch.setattr(
        "app.modules.market_data.providers.commodities_adapter._QueuedAlphaVantageProvider.fetch_instruments",
        _alpha_fetch,
    )
    monkeypatch.setattr(
        "app.modules.market_data.providers.commodities_adapter._QueuedYahooProvider.fetch_instruments",
        _yahoo_fetch,
    )
    monkeypatch.setattr(
        "app.modules.market_data.providers.commodities_adapter.Settings",
        lambda: SimpleNamespace(
            market_data_commodities_url="",
            goldapi_key="",
            alpha_vantage_key="test-key",
        ),
    )

    from app.modules.market_data.providers.commodities_adapter import fetch_commodities_normalized

    result = await fetch_commodities_normalized(
        retry_attempts=0,
        requested_symbols=frozenset({"XAU", "WTI", "XPD", "MISSING"}),
    )

    assert call_order[0] == "goldapi"
    assert "alpha_vantage" in call_order
    assert "yahoo" in call_order
    by_symbol = {dto.symbol: dto.provider_source for dto in result}
    assert by_symbol == {
        "XAU": "goldapi",
        "WTI": "alpha_vantage",
        "XPD": "yahoo",
    }
    assert "MISSING" not in by_symbol


@pytest.mark.asyncio
async def test_commodities_ingest_source_already_real(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Commodities ingest already maps provider source (not custom hardcode)."""
    from app.modules.market_data.ingestion import CommodityIngestItem

    monkeypatch.setattr(
        "app.modules.market_data.fetching.fetch_forex_rates",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.modules.market_data.fetching.fetch_crypto_prices",
        AsyncMock(return_value=([], False)),
    )
    monkeypatch.setattr(
        "app.modules.market_data.fetching.fetch_commodities",
        AsyncMock(
            return_value=(
                [
                    {
                        "symbol": "XAU",
                        "name": "Gold",
                        "price": 2400.0,
                        "unit": "oz",
                        "change_24h": 0.5,
                        "source": "yahoo",
                    },
                ],
                None,
                False,
            ),
        ),
    )
    monkeypatch.setattr(
        "app.modules.market_data.ingestion.Settings",
        lambda: SimpleNamespace(forex_allowed_currency_set={"EUR"}),
    )

    service = IngestionService(MagicMock())
    service.persist_commodities = MagicMock(return_value=1)

    await service.ingest_all(include_commodities=True)

    items = service.persist_commodities.call_args.args[0]
    assert len(items) == 1
    assert isinstance(items[0], CommodityIngestItem)
    assert items[0].source == "yahoo"


def test_fuel_route_and_module_removed() -> None:
    """Dead fuel and per-class market read paths are removed from API surface."""
    import importlib

    from app.modules.market_data import api as market_api

    paths = {route.path for route in market_api.router.routes}
    assert "/markets/fuel" not in paths
    for dead in (
        "/markets/forex",
        "/markets/crypto",
        "/markets/commodities",
        "/markets/refresh-metadata",
    ):
        assert dead not in paths

    with pytest.raises(ImportError):
        importlib.import_module("app.modules.market_data.fuel")
    with pytest.raises(ImportError):
        importlib.import_module("app.modules.market_data.providers.fuel_adapter")
