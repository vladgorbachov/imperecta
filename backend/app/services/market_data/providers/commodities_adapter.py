"""Commodities provider. Configurable HTTP source. Returns empty if URL not set."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.config import Settings
from app.services.market_data.dto import NormalizedCommodity
from app.services.market_data.providers.base import CommoditiesProviderAdapter

logger = logging.getLogger(__name__)


class CommoditiesHttpAdapter(CommoditiesProviderAdapter):
    """
    Commodities HTTP adapter. Expects JSON array with symbol, price, change_24h, unit.
    Set MARKET_DATA_COMMODITIES_URL to enable. Returns empty list if not configured.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        self.base_url = (base_url or Settings().market_data_commodities_url).strip()
        self.timeout = timeout

    async def fetch(self) -> list[NormalizedCommodity]:
        """Fetch commodities. Returns empty if URL not configured."""
        if not self.base_url:
            logger.debug("Commodities URL not configured, skipping")
            return []

        refreshed_at = datetime.now(timezone.utc)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(self.base_url)
            resp.raise_for_status()
            data = resp.json()

        if not isinstance(data, list):
            logger.warning("Commodities response not a list: %s", type(data))
            return []

        items: list[NormalizedCommodity] = []
        for row in data:
            try:
                symbol = str(row.get("symbol", ""))[:20]
                price = Decimal(str(row.get("price", 0)))
                change = row.get("change_24h")
                change_24h = float(change) if change is not None else None
                name = row.get("name")
                unit = row.get("unit")
                items.append(
                    NormalizedCommodity(
                        symbol=symbol,
                        name=str(name) if name else None,
                        price=price,
                        change_24h=change_24h,
                        unit=str(unit)[:20] if unit else None,
                        refreshed_at=refreshed_at,
                    )
                )
            except Exception as e:
                logger.warning("Parse commodity row: %s", e)
                continue

        logger.info("Commodities adapter fetched %d items", len(items))
        return items
