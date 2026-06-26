"""Fetch decision + page fetch for discovery (mirrors scrape _layer_order path)."""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.models.dimensions import DimMarketplace
from app.modules.scraper.scraper_pool import ScraperPool


def fetch_params_from_marketplace(marketplace: DimMarketplace) -> tuple[bool, int]:
    """Return requires_js and scrape_tier using the same expressions as scrape."""
    requires_js = bool(marketplace.requires_js)
    scrape_tier = int(marketplace.scrape_tier) if marketplace.scrape_tier is not None else 1
    return requires_js, scrape_tier


async def fetch_page(
    pool: ScraperPool,
    url: str,
    *,
    requires_js: bool,
    scrape_tier: int,
    accept_language: str | None = None,
) -> tuple[str | None, BeautifulSoup | None]:
    """Fetch a page via scrape's full backend chain (_layer_order), not static-only."""
    return await pool.scrape_page_for_analysis(
        url,
        requires_js=requires_js,
        scrape_tier=scrape_tier,
        static_fetch=False,
        accept_language=accept_language,
    )
