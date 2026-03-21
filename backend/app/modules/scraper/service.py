"""Global pool scraping: FactListing → FactPrice, DimProduct enrichment."""

import logging
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing, FactPrice
from app.modules.scraper.engine import ScrapeResult, ScraperFactory
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool

logger = logging.getLogger(__name__)


def _normalize_product_name(raw: str) -> str:
    s = (raw or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s[:500]


async def _today_date_id(db: AsyncSession) -> int:
    """YYYYMMDD surrogate for dim_date; ensures row exists for FK on fact_price."""
    from app.models.dimensions import DimDate

    today = datetime.now(timezone.utc).date()
    date_id = int(today.strftime("%Y%m%d"))
    exists = await db.scalar(select(DimDate.date_id).where(DimDate.date_id == date_id))
    if exists is not None:
        return date_id
    # Minimal dim_date row for ingestion/scrape paths when calendar not pre-seeded.
    import calendar

    iso_year, iso_week, iso_weekday = today.isocalendar()
    row = DimDate(
        date_id=date_id,
        full_date=today,
        year=today.year,
        quarter=(today.month - 1) // 3 + 1,
        month=today.month,
        month_name=today.strftime("%B"),
        week_iso=iso_week,
        day_of_month=today.day,
        day_of_week=iso_weekday,
        day_name=today.strftime("%A"),
        is_weekend=iso_weekday >= 6,
        is_last_day_of_month=today.day == calendar.monthrange(today.year, today.month)[1],
    )
    db.add(row)
    await db.flush()
    return date_id


async def _previous_price_snapshot(
    db: AsyncSession,
    listing_id: UUID,
    before_date_id: int,
) -> float | None:
    """Latest prior fact_price.price for change_pct."""
    row = await db.execute(
        select(FactPrice.price)
        .where(FactPrice.listing_id == listing_id, FactPrice.date_id < before_date_id)
        .order_by(FactPrice.date_id.desc())
        .limit(1),
    )
    val = row.scalar_one_or_none()
    return float(val) if val is not None else None


class GlobalScrapeService:
    """Scrape pool listings and persist FactPrice + listing denormalized fields."""

    def __init__(self, db: AsyncSession, scraper_pool: ScraperPool):
        self.db = db
        self.pool = scraper_pool

    async def scrape_product(self, listing_id: UUID) -> PoolScrapeResult:
        """Scrape a single listing and save to fact_price."""
        listing = await self.db.get(FactListing, listing_id)
        if not listing:
            return PoolScrapeResult(success=False, url="", error="listing_not_found")

        mp = await self.db.get(DimMarketplace, listing.marketplace_id)
        requires_js = bool(mp.requires_js) if mp else False

        cfg = listing.scraper_config if isinstance(listing.scraper_config, dict) else {}
        custom_selectors = {
            k: v
            for k, v in {
                "title": cfg.get("title") or (mp.custom_title_selector if mp else None),
                "price": cfg.get("price") or (mp.custom_price_selector if mp else None),
                "image": cfg.get("image"),
                "original_price": cfg.get("original_price"),
            }.items()
            if v
        }

        result = await self.pool.scrape_product(
            url=listing.external_url,
            custom_selectors=custom_selectors if custom_selectors else None,
            requires_js=requires_js,
        )

        if not result.success or not result.data:
            listing.consecutive_errors = (listing.consecutive_errors or 0) + 1
            listing.last_error = result.error or "scrape_failed"
            try:
                await self.db.commit()
            except Exception as exc:
                logger.error("Failed to save scrape error state: %s", exc)
                await self.db.rollback()
            return result

        data = result.data
        now = datetime.now(timezone.utc)
        listing.last_price = data.price
        listing.last_currency_code = (data.currency or "USD")[:3]
        listing.last_in_stock = True
        listing.last_checked_at = now
        listing.consecutive_errors = 0
        listing.last_error = None

        product = await self.db.get(DimProduct, listing.product_id)
        if product:
            if data.title and (not product.name or product.name == listing.external_url):
                product.name = data.title[:500]
                product.name_normalized = _normalize_product_name(data.title)
            if data.image_url and not product.image_url:
                product.image_url = data.image_url

        date_id = await _today_date_id(self.db)
        await self.db.execute(
            delete(FactPrice).where(
                FactPrice.listing_id == listing.id,
                FactPrice.date_id == date_id,
            ),
        )
        prev = await _previous_price_snapshot(self.db, listing.id, date_id)
        price_change_pct = None
        if prev is not None and prev > 0 and data.price is not None:
            price_change_pct = round((float(data.price) - prev) / prev * 100.0, 4)

        price_record = FactPrice(
            listing_id=listing.id,
            date_id=date_id,
            price=float(data.price),
            currency_code=(data.currency or "USD")[:3],
            original_price=float(data.original_price) if data.original_price else None,
            in_stock=True,
            scraped_at=now,
            price_change_pct=price_change_pct,
        )
        self.db.add(price_record)

        try:
            await self.db.commit()
        except Exception as exc:
            logger.error("Failed to save price: %s", exc)
            await self.db.rollback()
            return PoolScrapeResult(
                success=False,
                url=listing.external_url,
                data=data,
                error="persist_failed",
            )

        return result

    async def get_stale_products(self, limit: int = 500) -> list[UUID]:
        """Listings that need refresh (oldest last_checked_at first)."""
        threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt = (
            select(FactListing.id)
            .where(FactListing.is_active.is_(True))
            .where(
                (FactListing.last_checked_at.is_(None)) | (FactListing.last_checked_at < threshold),
            )
            .order_by(FactListing.last_checked_at.asc().nullsfirst())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [r[0] for r in result.all()]

    async def recalculate_analytics(self, product_id: UUID) -> None:
        """Hook for downstream analytics refresh (no-op until materialized views)."""
        _ = product_id

    async def find_incomplete_products(self, limit: int = 100) -> list[UUID]:
        """Listings missing price or image (enrichment backlog)."""
        stmt = (
            select(FactListing.id)
            .join(DimProduct, FactListing.product_id == DimProduct.id)
            .where(FactListing.is_active.is_(True))
            .where((FactListing.last_price.is_(None)) | (DimProduct.image_url.is_(None)))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [r[0] for r in result.all()]


def _detect_scraper_type(url: str, scraper_type_field: str | None) -> str:
    return "universal"


def _get_scraper(scraper_type: str, css_selector_price: str | None):
    return ScraperFactory.create(
        scraper_type,
        css_selector_price=css_selector_price,
    )


async def scrape_competitor_product(
    competitor_product_id: UUID,
    db: AsyncSession,
) -> ScrapeResult:
    """Legacy competitor scrape removed; use FactListing + GlobalScrapeService."""
    raise NotImplementedError("Use GlobalScrapeService.scrape_product(listing_id)")
