"""Metals Gold API -> Yahoo failover tests."""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.modules.market_data.providers.commodities_adapter import (
    METAL_YAHOO_SYMBOLS,
    CommoditiesUnifiedAdapter,
    _quantize_commodity_price,
)


@pytest.fixture
def adapter(monkeypatch: pytest.MonkeyPatch) -> CommoditiesUnifiedAdapter:
    monkeypatch.setattr(
        "app.modules.market_data.providers.commodities_adapter.Settings",
        lambda: SimpleNamespace(
            market_data_commodities_url="",
            goldapi_key="",
            alpha_vantage_key="",
        ),
    )
    return CommoditiesUnifiedAdapter(timeout=5.0, retry_attempts=0)


@pytest.mark.asyncio
async def test_fetch_metal_falls_back_to_yahoo_when_gold_api_fails(
    adapter: CommoditiesUnifiedAdapter,
) -> None:
    refreshed_at = datetime(2026, 6, 25, tzinfo=timezone.utc)
    client = AsyncMock(spec=httpx.AsyncClient)

    yahoo_response = MagicMock()
    yahoo_response.raise_for_status = MagicMock()
    yahoo_response.json.return_value = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": 3998.5,
                        "previousClose": 3980.0,
                    }
                }
            ]
        }
    }

    async def fake_get(url: str, **kwargs: object) -> MagicMock:
        if "gold-api.com" in url:
            raise httpx.TimeoutException("gold down")
        if "GC=F" in url:
            return yahoo_response
        raise AssertionError(f"unexpected url {url}")

    client.get = fake_get

    item = await adapter._fetch_metal(
        client,
        symbol="XAU",
        name="Gold",
        unit="oz",
        refreshed_at=refreshed_at,
    )

    assert item is not None
    assert item.symbol == "XAU"
    assert item.name == "Gold"
    assert item.unit == "oz"
    assert item.price == Decimal("3998.5000")
    assert item.change_24h is not None
    assert item.provider_source == "yahoo"


@pytest.mark.asyncio
async def test_fetch_metal_skips_symbol_when_both_sources_fail(
    adapter: CommoditiesUnifiedAdapter,
) -> None:
    refreshed_at = datetime(2026, 6, 25, tzinfo=timezone.utc)
    client = AsyncMock(spec=httpx.AsyncClient)

    async def fake_get(url: str, **kwargs: object) -> MagicMock:
        raise httpx.ConnectError("network down")

    client.get = fake_get

    item = await adapter._fetch_metal(
        client,
        symbol="XAG",
        name="Silver",
        unit="oz",
        refreshed_at=refreshed_at,
    )
    assert item is None


def test_metal_yahoo_symbol_map_covers_all_metals() -> None:
    metals = {"XAU", "XAG", "XPT", "XPD"}
    assert set(METAL_YAHOO_SYMBOLS) == metals


def test_quantize_commodity_price_rounds_to_four_decimals() -> None:
    assert _quantize_commodity_price(Decimal("1234.56789")) == Decimal("1234.5679")
