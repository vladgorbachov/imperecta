"""Price monitoring service: scrape and save price snapshots."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompetitorProduct, PriceSnapshot, Product
from app.scrapers import ScrapeResult, ScraperFactory


def _detect_scraper_type(url: str, scraper_type_field: str | None) -> str:
    """Always returns 'universal'. Kept for API compatibility."""
    return "universal"


def _get_scraper(scraper_type: str, css_selector_price: str | None):
    """Get scraper instance. Always returns UniversalScraper."""
    return ScraperFactory.create(
        scraper_type,
        css_selector_price=css_selector_price,
    )


async def scrape_competitor_product(
    competitor_product_id: UUID,
    db: AsyncSession,
) -> ScrapeResult:
    """
    Scrape competitor product, save PriceSnapshot, update CompetitorProduct.
    Returns ScrapeResult.
    """
    result = await db.execute(
        select(CompetitorProduct, Product)
        .join(Product, CompetitorProduct.product_id == Product.id)
        .where(CompetitorProduct.id == competitor_product_id)
    )
    row = result.one_or_none()
    if not row:
        raise ValueError("Competitor product not found")

    cp, product = row
    scraper_type = _detect_scraper_type(cp.url, cp.scraper_type)
    scraper = _get_scraper(scraper_type, cp.css_selector_price)

    data = await scraper.scrape(cp.url)

    now = datetime.now(timezone.utc)

    snapshot = PriceSnapshot(
        competitor_product_id=cp.id,
        price=data.price,
        old_price=data.old_price,
        promo_label=data.promo_label,
        in_stock=data.in_stock if data.in_stock is not None else True,
    )
    db.add(snapshot)
    await db.flush()

    cp.last_price = data.price
    cp.last_promo_label = data.promo_label
    cp.last_in_stock = data.in_stock
    cp.last_checked_at = now
    if data.product_name and not cp.name:
        cp.name = data.product_name[:500]

    await db.flush()

    return data
