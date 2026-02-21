"""Price monitoring service: scrape and save price snapshots."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompetitorProduct, PriceSnapshot, Product
from app.scrapers.base import ScrapedData
from app.scrapers.generic_web import GenericWebScraper
from app.scrapers.ozon import OzonScraper
from app.scrapers.wildberries import WildberriesScraper


def _detect_scraper_type(url: str, scraper_type_field: str | None) -> str:
    """Auto-detect scraper type from URL or use field value."""
    if scraper_type_field and scraper_type_field != "auto":
        return scraper_type_field
    url_lower = url.lower()
    if "ozon.ru" in url_lower:
        return "ozon"
    if "wildberries.ru" in url_lower or "wb.ru" in url_lower:
        return "wildberries"
    return "generic"


def _get_scraper(scraper_type: str, css_selector_price: str | None):
    """Get scraper instance by type."""
    if scraper_type == "ozon":
        return OzonScraper()
    if scraper_type == "wildberries":
        return WildberriesScraper()
    return GenericWebScraper(css_selector_price=css_selector_price)


async def scrape_competitor_product(
    competitor_product_id: UUID,
    db: AsyncSession,
) -> ScrapedData:
    """
    Scrape competitor product, save PriceSnapshot, update CompetitorProduct.
    Returns ScrapedData.
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
        in_stock=data.in_stock,
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
