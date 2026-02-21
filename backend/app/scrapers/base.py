"""Abstract base scraper class with retry logic and delays."""

import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ScrapedData:
    """Result of price scraping."""

    price: Decimal
    old_price: Decimal | None
    promo_label: str | None
    in_stock: bool
    product_name: str | None


class AbstractScraper(ABC):
    """Abstract base class for marketplace scrapers with retries and delays."""

    MAX_RETRIES = 3
    DELAY_MIN = 1
    DELAY_MAX = 3

    async def _random_delay(self) -> None:
        """Random delay between requests (1-3 sec)."""
        delay = random.uniform(self.DELAY_MIN, self.DELAY_MAX)
        await asyncio.sleep(delay)

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff: 2^attempt seconds."""
        return 2**attempt

    async def scrape(self, url: str) -> ScrapedData:
        """Scrape with retries (3 attempts, exponential backoff)."""
        last_error: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            await self._random_delay()
            try:
                return await self._scrape_impl(url)
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    backoff = self._backoff_delay(attempt)
                    await asyncio.sleep(backoff)
        raise last_error or RuntimeError("Scrape failed")

    @abstractmethod
    async def _scrape_impl(self, url: str) -> ScrapedData:
        """Implement actual scraping logic. Called by scrape() with retries."""
        pass
