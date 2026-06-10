"""Unified commodities provider (Gold API + Alpha Vantage/Yahoo fallback)."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.config import Settings
from app.modules.market_data.dto import NormalizedCommodity
from app.modules.market_data.providers.base import CommoditiesProviderAdapter

logger = logging.getLogger(__name__)


GOLD_API_DEFAULT_BASE_URL = "https://api.gold-api.com/price"
ALPHA_VANTAGE_QUERY_URL = "https://www.alphavantage.co/query"
YAHOO_CHART_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

METAL_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("XAU", "Gold", "oz"),
    ("XAG", "Silver", "oz"),
    ("XPT", "Platinum", "oz"),
    ("XPD", "Palladium", "oz"),
)

ENERGY_ITEMS: tuple[tuple[str, str, str, str], ...] = (
    ("WTI", "Crude Oil (WTI)", "bbl", "CL=F"),
    ("BRENT", "Crude Oil (Brent)", "bbl", "BZ=F"),
)


class CommoditiesUnifiedAdapter(CommoditiesProviderAdapter):
    """
    Unified commodities adapter aligned with Chrome extension data flow:
    - metals: Gold API
    - energy: Alpha Vantage, fallback to Yahoo Finance chart endpoint
    """

    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        settings = Settings()
        configured_base = (base_url or settings.market_data_commodities_url or "").strip()
        self.base_url = configured_base or GOLD_API_DEFAULT_BASE_URL
        self.gold_api_key = (settings.goldapi_key or "").strip()
        self.alpha_vantage_key = (settings.alpha_vantage_key or "").strip()
        self.timeout = timeout

    async def fetch(self) -> list[NormalizedCommodity]:
        """Fetch commodities from unified source chain."""
        refreshed_at = datetime.now(timezone.utc)
        items: list[NormalizedCommodity] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for symbol, name, unit in METAL_ITEMS:
                item = await self._fetch_metal(client, symbol=symbol, name=name, unit=unit, refreshed_at=refreshed_at)
                if item is not None:
                    items.append(item)

            for symbol, name, unit, yahoo_symbol in ENERGY_ITEMS:
                item = await self._fetch_energy(
                    client,
                    symbol=symbol,
                    name=name,
                    unit=unit,
                    yahoo_symbol=yahoo_symbol,
                    refreshed_at=refreshed_at,
                )
                if item is not None:
                    items.append(item)

        logger.info("Commodities adapter fetched %d items", len(items))
        return items

    async def _fetch_metal(
        self,
        client: httpx.AsyncClient,
        *,
        symbol: str,
        name: str,
        unit: str,
        refreshed_at: datetime,
    ) -> NormalizedCommodity | None:
        url = f"{self.base_url.rstrip('/')}/{symbol}"
        headers: dict[str, str] = {}
        if self.gold_api_key:
            headers["x-access-token"] = self.gold_api_key

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
            price_raw = payload.get("price", payload.get("close"))
            price = Decimal(str(price_raw))
            change_raw = payload.get("chp", payload.get("change_24h"))
            change_24h = float(change_raw) if change_raw is not None else None
            return NormalizedCommodity(
                symbol=symbol,
                name=name,
                price=price,
                change_24h=change_24h,
                unit=unit,
                refreshed_at=refreshed_at,
            )
        except Exception as error:
            logger.warning("Gold API fetch failed for %s: %s", symbol, error)
            return None

    async def _fetch_energy(
        self,
        client: httpx.AsyncClient,
        *,
        symbol: str,
        name: str,
        unit: str,
        yahoo_symbol: str,
        refreshed_at: datetime,
    ) -> NormalizedCommodity | None:
        alpha_item = await self._fetch_energy_from_alpha_vantage(
            client,
            symbol=symbol,
            name=name,
            unit=unit,
            refreshed_at=refreshed_at,
        )
        if alpha_item is not None:
            return alpha_item
        return await self._fetch_energy_from_yahoo(
            client,
            symbol=symbol,
            name=name,
            unit=unit,
            yahoo_symbol=yahoo_symbol,
            refreshed_at=refreshed_at,
        )

    async def _fetch_energy_from_alpha_vantage(
        self,
        client: httpx.AsyncClient,
        *,
        symbol: str,
        name: str,
        unit: str,
        refreshed_at: datetime,
    ) -> NormalizedCommodity | None:
        if not self.alpha_vantage_key:
            return None
        try:
            response = await client.get(
                ALPHA_VANTAGE_QUERY_URL,
                params={
                    "function": symbol,
                    "interval": "daily",
                    "apikey": self.alpha_vantage_key,
                },
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("Error Message") or payload.get("Note"):
                return None
            rows = payload.get("data")
            if not isinstance(rows, list) or len(rows) < 2:
                return None
            latest = Decimal(str(rows[0].get("value")))
            previous = Decimal(str(rows[1].get("value")))
            change_24h = None
            if previous != 0:
                change_24h = float(((latest - previous) / previous) * 100)
            return NormalizedCommodity(
                symbol=symbol,
                name=name,
                price=latest,
                change_24h=change_24h,
                unit=unit,
                refreshed_at=refreshed_at,
            )
        except Exception:
            return None

    async def _fetch_energy_from_yahoo(
        self,
        client: httpx.AsyncClient,
        *,
        symbol: str,
        name: str,
        unit: str,
        yahoo_symbol: str,
        refreshed_at: datetime,
    ) -> NormalizedCommodity | None:
        try:
            response = await client.get(
                f"{YAHOO_CHART_BASE_URL.rstrip('/')}/{yahoo_symbol}",
                params={"interval": "1d", "range": "5d"},
            )
            response.raise_for_status()
            payload = response.json()
            result = (((payload.get("chart") or {}).get("result") or [None])[0] or {})
            meta = result.get("meta") or {}
            latest_raw = meta.get("regularMarketPrice", meta.get("previousClose"))
            previous_raw = meta.get("previousClose")
            latest = Decimal(str(latest_raw))
            previous = Decimal(str(previous_raw)) if previous_raw is not None else None
            change_24h = None
            if previous is not None and previous != 0:
                change_24h = float(((latest - previous) / previous) * 100)
            return NormalizedCommodity(
                symbol=symbol,
                name=name,
                price=latest,
                change_24h=change_24h,
                unit=unit,
                refreshed_at=refreshed_at,
            )
        except Exception as error:
            logger.warning("Yahoo fallback failed for %s (%s): %s", symbol, yahoo_symbol, error)
            return None
