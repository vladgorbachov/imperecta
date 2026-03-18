"""Scraper services: global pool scraping and competitor product scraping."""

import logging
import statistics
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompetitorProduct, PriceSnapshot, Product
from app.modules.marketplaces.models import AdminMarketplace
from app.modules.product_pool.models import GlobalPriceSnapshot, GlobalProduct
from app.modules.scraper.engine import ScrapeResult, ScraperFactory
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool

logger = logging.getLogger(__name__)
MAX_VALID_PRICE = 9_999_999_999.99  # Max for Numeric(12,2)


class GlobalScrapeService:
    def __init__(self, db: AsyncSession, scraper_pool: ScraperPool):
        self.db = db
        self.pool = scraper_pool

    async def scrape_product(self, product_id: int) -> PoolScrapeResult:
        product = await self.db.get(GlobalProduct, product_id)
        if product is None:
            return PoolScrapeResult(
                success=False,
                url="",
                error="product_not_found",
            )

        marketplace = await self.db.get(AdminMarketplace, product.marketplace_id)
        selectors = {
            "title": getattr(marketplace, "custom_title_selector", None) if marketplace else None,
            "price": getattr(marketplace, "custom_price_selector", None) if marketplace else None,
            "image": getattr(marketplace, "custom_image_selector", None) if marketplace else None,
            "original_price": None,
        }
        requires_js = bool(getattr(marketplace, "requires_js", False))
        result = await self.pool.scrape_product(
            url=product.url,
            custom_selectors=selectors,
            requires_js=requires_js,
        )

        now = datetime.now(timezone.utc)
        product.last_scraped_at = now
        product.last_scraper_layer = result.scraper_layer

        if result.success and result.data:
            data = result.data
            price = data.price
            if price is not None:
                if price > MAX_VALID_PRICE or price <= 0:
                    logger.warning(
                        "Price overflow or invalid %.2f for %s, discarding",
                        price,
                        product.url[:80],
                    )
                    price = None
            product.title = data.title or product.title
            product.description = data.description or product.description
            product.image_url = data.image_url or product.image_url
            product.current_price = price if price is not None else product.current_price
            product.original_price = (
                data.original_price if data.original_price is not None else product.original_price
            )
            if data.currency:
                product.currency = data.currency
            product.status = "active"
            product.scrape_error_count = 0

            if price is not None:
                snapshot = GlobalPriceSnapshot(
                    global_product_id=product.id,
                    price=price,
                    original_price=data.original_price,
                    currency=data.currency or product.currency or "USD",
                    scraper_layer=result.scraper_layer,
                )
                self.db.add(snapshot)
        else:
            product.scrape_error_count = int(product.scrape_error_count or 0) + 1
            if product.scrape_error_count > 10:
                product.status = "failed"
            elif product.status == "pending":
                product.status = "retry"

        await self.db.flush()
        await self.recalculate_analytics(product.id)
        try:
            await self.db.commit()
        except Exception as e:
            logger.error("Failed to save scrape result for %s: %s", product.url[:80], e)
            await self.db.rollback()
        return result

    async def get_stale_products(self, limit: int = 500) -> list[GlobalProduct]:
        stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
        stmt = (
            select(GlobalProduct)
            .where((GlobalProduct.scrape_error_count <= 10) | (GlobalProduct.scrape_error_count.is_(None)))
            .where(
                (GlobalProduct.last_scraped_at.is_(None))
                | (GlobalProduct.last_scraped_at <= stale_cutoff)
                | (GlobalProduct.status == "pending")
            )
            .order_by(
                case((GlobalProduct.status == "pending", 0), else_=1),
                GlobalProduct.last_scraped_at.asc().nullsfirst(),
            )
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def recalculate_analytics(self, product_id: int):
        product = await self.db.get(GlobalProduct, product_id)
        if product is None:
            return

        stmt = (
            select(GlobalPriceSnapshot)
            .where(GlobalPriceSnapshot.global_product_id == product_id)
            .order_by(GlobalPriceSnapshot.scraped_at.asc())
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        if len(rows) < 2:
            return

        now = datetime.now(timezone.utc)
        latest = rows[-1].price

        def _latest_before(days: int):
            threshold = now - timedelta(days=days)
            candidates = [r for r in rows if r.scraped_at and r.scraped_at <= threshold]
            return candidates[-1].price if candidates else None

        def _pct_change(old_value):
            if old_value is None or float(old_value) == 0:
                return None
            return ((float(latest) - float(old_value)) / float(old_value)) * 100.0

        product.price_change_pct_24h = _pct_change(_latest_before(1))
        product.price_change_pct_7d = _pct_change(_latest_before(7))
        product.price_change_pct_30d = _pct_change(_latest_before(30))

        prices = [float(r.price) for r in rows[-90:] if r.price is not None]
        if len(prices) >= 2 and statistics.mean(prices) > 0:
            stddev = statistics.pstdev(prices)
            mean = statistics.mean(prices)
            product.volatility_30d = (stddev / mean) * 100.0

        await self.db.flush()

    async def find_incomplete_products(self, limit: int = 100) -> list[GlobalProduct]:
        stmt = (
            select(GlobalProduct)
            .where(
                (GlobalProduct.title.is_(None))
                | (GlobalProduct.current_price.is_(None))
                | (GlobalProduct.image_url.is_(None))
            )
            .where((GlobalProduct.scrape_error_count < 3) | (GlobalProduct.scrape_error_count.is_(None)))
            .order_by(GlobalProduct.updated_at.asc().nullsfirst())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


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

    cp, _product = row
    scraper_type = _detect_scraper_type(cp.url, cp.scraper_type)
    scraper = _get_scraper(scraper_type, cp.css_selector_price)

    data = await scraper.scrape(cp.url)

    now = datetime.now(timezone.utc)
    snapshot = PriceSnapshot(
        competitor_product_id=cp.id,
        price=Decimal(str(data.price)) if data.price is not None else None,
        old_price=Decimal(str(data.old_price)) if data.old_price is not None else None,
        promo_label=data.promo_label,
        in_stock=data.in_stock if data.in_stock is not None else True,
    )
    db.add(snapshot)
    await db.flush()

    cp.last_price = Decimal(str(data.price)) if data.price is not None else None
    cp.last_promo_label = data.promo_label
    cp.last_in_stock = data.in_stock
    cp.last_checked_at = now
    if data.product_name and not cp.name:
        cp.name = data.product_name[:500]

    await db.flush()
    return data
