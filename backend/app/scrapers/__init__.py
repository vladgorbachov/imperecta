"""
Imperecta scraping engine.

Usage:
    from app.scrapers import ScraperFactory, ScrapeResult
    scraper = ScraperFactory.create("ozon")
    result = await scraper.scrape(url)
"""

from app.scrapers.engine import (
    BaseScraper,
    GenericWebScraper,
    OzonScraper,
    ScrapeResult,
    ScraperFactory,
    WildberriesScraper,
)
from app.scrapers.proxy_manager import ProxyManager, proxy_manager

__all__ = [
    "BaseScraper",
    "GenericWebScraper",
    "OzonScraper",
    "ScrapeResult",
    "ScraperFactory",
    "WildberriesScraper",
    "ProxyManager",
    "proxy_manager",
]
