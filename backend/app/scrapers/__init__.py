"""
Imperecta scraping engine.

Usage:
    from app.scrapers import ScraperFactory, ScrapeResult
    scraper = ScraperFactory.create("universal")
    result = await scraper.scrape(url)
"""

from app.scrapers.engine import (
    BaseScraper,
    ScrapeResult,
    ScraperFactory,
    UniversalScraper,
)
from app.scrapers.proxy_manager import ProxyManager, proxy_manager

__all__ = [
    "BaseScraper",
    "ScrapeResult",
    "ScraperFactory",
    "UniversalScraper",
    "ProxyManager",
    "proxy_manager",
]
