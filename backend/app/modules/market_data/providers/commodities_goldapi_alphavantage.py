"""Commodities adapter: GoldAPI (metals) + Alpha Vantage (energy). No static data."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from app.modules.market_data.dto import NormalizedCommodity
from app.modules.market_data.providers.base import CommoditiesProviderAdapter
from app.modules.market_data.service import fetch_energy, fetch_metals

logger = logging.getLogger(__name__)


class CommoditiesGoldAPIAlphaVantageAdapter(CommoditiesProviderAdapter):
    """
    Fetches commodities from GoldAPI (XAU, XAG, XPT, XPD) and Alpha Vantage (WTI, Brent, Natural Gas).
    Metals cache: 36h. Energy cache: 24h.
    Returns empty list if both APIs fail or keys not configured.
    """

    async def fetch(self) -> list[NormalizedCommodity]:
        """Fetch metals and energy, merge into normalized list."""
        metals = await fetch_metals()
        energy = await fetch_energy()

        items = metals.get("items", []) + energy.get("items", [])
        errors = [error for error in [metals.get("error"), energy.get("error")] if error]
        if errors:
            logger.warning("Commodities fetch partial: %s", "; ".join(errors))

        refreshed_at = datetime.now(timezone.utc)
        result: list[NormalizedCommodity] = []
        for row in items:
            try:
                result.append(
                    NormalizedCommodity(
                        symbol=str(row.get("symbol", ""))[:20],
                        name=str(row["name"])[:100] if row.get("name") else None,
                        price=Decimal(str(row.get("price", 0))),
                        change_24h=float(row["change_24h"]) if row.get("change_24h") is not None else None,
                        unit=str(row["unit"])[:20] if row.get("unit") else None,
                        refreshed_at=refreshed_at,
                    )
                )
            except Exception as error:
                logger.warning("Parse commodity row: %s", error)
                continue

        logger.info("Commodities adapter fetched %d items (metals + energy)", len(result))
        return result
