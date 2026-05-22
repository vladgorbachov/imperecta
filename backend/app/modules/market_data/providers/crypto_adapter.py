"""Crypto provider: Binance primary, CoinGecko backup. 50 top coins."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.config import Settings
from app.modules.market_data.dto import NormalizedCrypto
from app.modules.market_data.providers.base import CryptoProviderAdapter
from app.modules.market_data.providers.binance_adapter import BinanceCryptoAdapter

logger = logging.getLogger(__name__)
COINGECKO_FALLBACK_URL = "https://api.coingecko.com/api/v3/coins/markets"


class CryptoCoingeckoAdapter(CryptoProviderAdapter):
    """CoinGecko markets adapter (backup). Normalizes to NormalizedCrypto."""

    def __init__(self, base_url: str | None = None, timeout: float = 15.0, per_page: int = 50):
        self.base_url = base_url or COINGECKO_FALLBACK_URL
        self.timeout = timeout
        self.per_page = per_page

    async def fetch(self) -> list[NormalizedCrypto]:
        """Fetch top coins from CoinGecko. Returns normalized list."""
        refreshed_at = datetime.now(timezone.utc)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                self.base_url,
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": self.per_page,
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

        logger.info("Crypto CoinGecko adapter fetched %d assets", len(items))
        return items


class CryptoCompositeAdapter(CryptoProviderAdapter):
    """Binance primary, CoinGecko fallback. Returns up to 50 crypto assets."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self._binance = BinanceCryptoAdapter(timeout=timeout)
        self._coingecko = CryptoCoingeckoAdapter(timeout=timeout, per_page=50)

    async def fetch(self) -> list[NormalizedCrypto]:
        """Fetch crypto: Binance primary, CoinGecko backup."""
        try:
            items = await self._binance.fetch()
            if items and len(items) >= 10:
                logger.info("Crypto from Binance: %d assets", len(items))
                return items
        except Exception as error:
            logger.warning("Binance crypto failed: %s, falling back to CoinGecko", error)

        try:
            items = await self._coingecko.fetch()
            logger.info("Crypto from CoinGecko (backup): %d assets", len(items))
            return items
        except Exception as error:
            logger.error("Both crypto sources failed: %s", error)
            return []


class CryptoUnifiedAdapter(CryptoProviderAdapter):
    """Unified crypto adapter: configured provider + Binance + CoinGecko chain."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self._configured_url = (Settings().market_data_crypto_url or "").strip()

    async def fetch(self) -> list[NormalizedCrypto]:
        adapters: list[CryptoProviderAdapter] = []
        if self._configured_url:
            adapters.append(CryptoCoingeckoAdapter(base_url=self._configured_url, timeout=self.timeout, per_page=50))
        adapters.append(CryptoCompositeAdapter(timeout=self.timeout))

        for adapter in adapters:
            try:
                items = await adapter.fetch()
                if items:
                    return items
            except Exception as error:
                logger.warning("Crypto provider %s failed: %s", adapter.__class__.__name__, error)
        return []
