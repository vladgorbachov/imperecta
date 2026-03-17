"""Forex provider: Frankfurter API. Free, no key required."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.config import Settings
from app.modules.market_data.dto import NormalizedForex
from app.modules.market_data.providers.base import ForexProviderAdapter

logger = logging.getLogger(__name__)


class ForexFrankfurterAdapter(ForexProviderAdapter):
    """Frankfurter API adapter. Normalizes to NormalizedForex."""

    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        self.base_url = base_url or Settings().market_data_forex_url
        self.timeout = timeout

    async def fetch(self) -> list[NormalizedForex]:
        """Fetch latest rates from Frankfurter. Returns normalized list."""
        refreshed_at = datetime.now(timezone.utc)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                self.base_url,
                params={"from": "EUR", "to": "USD,GBP,RUB,CHF,JPY"},
            )
            resp.raise_for_status()
            data = resp.json()

        if "rates" not in data:
            logger.warning("Frankfurter response missing 'rates': %s", data)
            return []

        items: list[NormalizedForex] = []
        base = data.get("base", "EUR")
        rates = data["rates"]
        for quote, rate in rates.items():
            try:
                rate_val = Decimal(str(rate))
                spread = Decimal("0.0001")
                items.append(
                    NormalizedForex(
                        symbol=f"{base}/{quote}",
                        bid=rate_val,
                        ask=rate_val + spread,
                        spread=spread,
                        change_24h=None,
                        refreshed_at=refreshed_at,
                    )
                )
            except Exception as error:
                logger.warning("Parse forex %s/%s: %s", base, quote, error)
                continue

        logger.info("Forex adapter fetched %d pairs", len(items))
        return items
