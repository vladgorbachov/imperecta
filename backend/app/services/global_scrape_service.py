"""
Orchestrates scraping for the global product pool.
Gets products from global_products → scrapes via ScraperPool → writes snapshots.
"""

from datetime import datetime, timedelta, timezone
import statistics

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_marketplace import AdminMarketplace
from app.models.global_product import GlobalPriceSnapshot, GlobalProduct
from app.scrapers.scraper_pool import PoolScrapeResult, ScraperPool


class GlobalScrapeService:
    def __init__(self, db: AsyncSession, scraper_pool: ScraperPool):
        self.db = db
        self.pool = scraper_pool

    async def scrape_product(self, product_id: int) -> PoolScrapeResult:
        """
        1. Load GlobalProduct by id
        2. Load its marketplace (for custom selectors, requires_js)
        3. Scrape via ScraperPool
        4. If success: write GlobalPriceSnapshot, update product fields
        5. If fail: increment scrape_error_count, set status if error_count > 10
        6. Recalculate price analytics (24h, 7d, 30d, volatility)
        """
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
            product.title = data.title or product.title
            product.description = data.description or product.description
            product.image_url = data.image_url or product.image_url
            product.current_price = data.price if data.price is not None else product.current_price
            product.original_price = (
                data.original_price if data.original_price is not None else product.original_price
            )
            if data.currency:
                product.currency = data.currency
            product.status = "active"
            product.scrape_error_count = 0

            if data.price is not None:
                snapshot = GlobalPriceSnapshot(
                    global_product_id=product.id,
                    price=data.price,
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
        await self.db.commit()
        return result

    async def get_stale_products(self, limit: int = 500) -> list[GlobalProduct]:
        """
        Products needing re-scrape.
        Priority: status="pending" first, then oldest last_scraped_at.
        Exclude: scrape_error_count > 10.
        """
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
        """Calculate price_change_pct and volatility from global_price_snapshots."""
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
        """Products with NULL title, price, or image_url AND scrape_error_count < 3."""
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
