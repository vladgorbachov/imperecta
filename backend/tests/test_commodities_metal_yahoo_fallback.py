"""Metals Gold API -> Yahoo failover tests (queue-provider architecture).

The old monolithic ``_fetch_metal`` fallback became two engine calls
sequenced by the provider queue: the Gold API provider returns None per
symbol on failure, and the Yahoo provider gap-fills the leftovers. These
tests pin the two engine halves the queue composes.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.modules.market_data.providers.commodities_adapter import (
    METAL_YAHOO_SYMBOLS,
    _CommodityFetchEngine,
)


@pytest.fixture
def engine() -> _CommodityFetchEngine:
    return _CommodityFetchEngine(
        base_url="https://api.gold-api.com/price",
        gold_api_key="",
        alpha_vantage_key="",
        timeout=5.0,
        retry_attempts=0,
        refreshed_at=datetime(2026, 6, 25, tzinfo=timezone.utc),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_gold_api_failure_yields_none_then_yahoo_gap_fills(
    engine: _CommodityFetchEngine,
) -> None:
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

    gold_item = await engine.fetch_metal_from_gold_api(
        client, symbol="XAU", name="Gold", unit="oz"
    )
    assert gold_item is None  # provider skips -> queue falls through

    item = await engine.fetch_from_yahoo_chart(
        client,
        symbol="XAU",
        name="Gold",
        unit="oz",
        yahoo_symbol=METAL_YAHOO_SYMBOLS["XAU"],
    )
    assert item is not None
    assert item.symbol == "XAU"
    assert item.name == "Gold"
    assert item.unit == "oz"
    assert item.price == Decimal("3998.5000")
    assert item.change_24h is not None
    assert item.provider_source == "yahoo"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_metal_skipped_when_both_sources_fail(
    engine: _CommodityFetchEngine,
) -> None:
    client = AsyncMock(spec=httpx.AsyncClient)

    async def fake_get(url: str, **kwargs: object) -> MagicMock:
        raise httpx.ConnectError("network down")

    client.get = fake_get

    assert (
        await engine.fetch_metal_from_gold_api(
            client, symbol="XAG", name="Silver", unit="oz"
        )
        is None
    )
    assert (
        await engine.fetch_from_yahoo_chart(
            client,
            symbol="XAG",
            name="Silver",
            unit="oz",
            yahoo_symbol=METAL_YAHOO_SYMBOLS["XAG"],
        )
        is None
    )
