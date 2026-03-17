"""Crypto provider: CoinGecko API. Free, no key required."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.config import Settings
from app.modules.market_data.dto import NormalizedCrypto
from app.modules.market_data.providers.base import CryptoProviderAdapter

logger = logging.getLogger(__name__)


class CryptoCoingeckoAdapter(CryptoProviderAdapter):
    """CoinGecko markets adapter. Normalizes to NormalizedCrypto."""

    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        self.base_url = base_url or Settings().market_data_crypto_url
        self.timeout = timeout

    async def fetch(self) -> list[NormalizedCrypto]:
        """Fetch top coins from CoinGecko. Returns normalized list."""
        refreshed_at = datetime.now(timezone.utc)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                self.base_url,
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 20,
                    "page": 1,
                    "sparkline": "false",
                    "price_change_percentage": "24h",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if not isinstance(data, list):
            logger.warning("CoinGecko response not a list: %s", type(data))
            return []

        items: list[NormalizedCrypto] = []
        for row in data:
            try:
                symbol = str(row.get("symbol", "")).upper()
                price = Decimal(str(row.get("current_price", 0)))
                change = row.get("price_change_percentage_24h")
                change_24h = float(change) if change is not None else None
                market_cap_raw = row.get("market_cap")
                market_cap = Decimal(str(market_cap_raw)) if market_cap_raw is not None else None
                items.append(
                    NormalizedCrypto(
                        symbol=symbol,
                        price=price,
                        change_24h=change_24h,
                        market_cap=market_cap,
                        refreshed_at=refreshed_at,
                    )
                )
            except Exception as error:
                logger.warning("Parse crypto row %s: %s", row.get("id"), error)
                continue

        logger.info("Crypto adapter fetched %d assets", len(items))
        return items
