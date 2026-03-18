"""
Binance API adapter for cryptocurrency market data.
Primary source: Binance public API (no key needed for market data).
Fetches top 50 trading pairs by 24h volume.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.modules.market_data.dto import NormalizedCrypto
from app.modules.market_data.providers.base import CryptoProviderAdapter

logger = logging.getLogger(__name__)

BINANCE_API_URL = "https://api.binance.com/api/v3"
TOP_N = 50


class BinanceCryptoAdapter(CryptoProviderAdapter):
    """Binance markets adapter. Returns top 50 USDT pairs by 24h volume."""

    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        self.base_url = base_url or BINANCE_API_URL
        self.timeout = timeout

    async def fetch(self) -> list[NormalizedCrypto]:
        """Fetch top 50 crypto from Binance ticker/24hr. Returns normalized list."""
        refreshed_at = datetime.now(timezone.utc)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}/ticker/24hr")
            resp.raise_for_status()
            tickers = resp.json()

        if not isinstance(tickers, list):
            logger.warning("Binance response not a list: %s", type(tickers))
            return []

        usdt_pairs = [
            t
            for t in tickers
            if isinstance(t, dict)
            and str(t.get("symbol", "")).endswith("USDT")
            and float(t.get("quoteVolume", 0)) > 0
        ]
        usdt_pairs.sort(
            key=lambda t: float(t.get("quoteVolume", 0)),
            reverse=True,
        )
        top = usdt_pairs[:TOP_N]

        items: list[NormalizedCrypto] = []
        for t in top:
            try:
                symbol = str(t["symbol"]).replace("USDT", "")
                price = Decimal(str(t.get("lastPrice", 0)))
                change_raw = t.get("priceChangePercent")
                change_24h = float(change_raw) if change_raw is not None else None
                items.append(
                    NormalizedCrypto(
                        symbol=symbol,
                        price=price,
                        change_24h=change_24h,
                        market_cap=None,
                        refreshed_at=refreshed_at,
                    )
                )
            except Exception as error:
                logger.warning("Binance parse error for %s: %s", t.get("symbol"), error)
                continue

        logger.info("Binance adapter fetched %d crypto assets", len(items))
        return items
