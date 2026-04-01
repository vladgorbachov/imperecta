"""Global pool scraping: FactListing → FactPrice, DimProduct enrichment."""

import asyncio
import logging
import re
from dataclasses import fields, is_dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.app_tables import ScrapeLog
from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing, FactPrice
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool

logger = logging.getLogger(__name__)


def _run_coro_in_worker(coro):
    """Fresh event loop for async pool I/O only (Celery fork + sync DB session)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


def _optional_in_stock(extracted: object | None) -> bool | None:
    """Availability is optional on extractor payloads; never invent True/False."""
    if extracted is None:
        return None
    raw = getattr(extracted, "in_stock", None)
    if raw is None or isinstance(raw, bool):
        return raw
    return None


def _payload_has_product_name_field(payload: object) -> bool:
    """True when extractor dataclass defines product_name (strict log rules apply)."""
    if not is_dataclass(payload):
        return False
    return any(f.name == "product_name" for f in fields(payload))


def _normalize_product_name(raw: str) -> str:
    s = (raw or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s[:500]


def _should_replace_placeholder_name(name: str | None, external_url: str) -> bool:
    """True if dim_product.name is a discovery placeholder; scraped title should replace it."""
    n = (name or "").strip()
    if not n or n.lower() == "product":
        return True
    if n == external_url:
        return True
    compact = n.replace(" ", "").replace("-", "").replace("_", "")
    if compact.isdigit():
        return True
    return False


def _today_date_id(db: Session) -> int:
    """YYYYMMDD surrogate for dim_date; ensures row exists for FK on fact_price.

    Deadlock-safe: SELECT first, INSERT ... ON CONFLICT DO NOTHING if missing,
    then SELECT again (idempotent; concurrent workers do not block on add+flush).
    """
    import calendar

    from app.models.dimensions import DimDate

    today = datetime.now(timezone.utc).date()
    date_id = int(today.strftime("%Y%m%d"))
    row_id = db.execute(
        select(DimDate.date_id).where(DimDate.date_id == date_id),
    ).scalar_one_or_none()
    if row_id is not None:
        return date_id

    _, iso_week, iso_weekday = today.isocalendar()
    stmt = (
        pg_insert(DimDate)
        .values(
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
            is_last_day_of_month=today.day
            == calendar.monthrange(today.year, today.month)[1],
        )
        .on_conflict_do_nothing(index_elements=["date_id"])
    )
    db.execute(stmt)
    db.flush()

    row_id = db.execute(
        select(DimDate.date_id).where(DimDate.date_id == date_id),
    ).scalar_one_or_none()
    if row_id is None:
        raise RuntimeError(f"dim_date row missing after upsert for date_id={date_id}")
    return date_id


def _previous_price_snapshot(
    db: Session,
    listing_id: UUID,
    before_date_id: int,
) -> float | None:
    """Latest prior fact_price.price for change_pct."""
    row = db.execute(
        select(FactPrice.price)
        .where(FactPrice.listing_id == listing_id, FactPrice.date_id < before_date_id)
        .order_by(FactPrice.date_id.desc())
        .limit(1),
    )
    val = row.scalar_one_or_none()
    return float(val) if val is not None else None


class GlobalScrapeService:
    """Scrape pool listings and persist FactPrice + listing denormalized fields."""

    def __init__(self, db: Session, scraper_pool: ScraperPool):
        self.db = db
        self.pool = scraper_pool

    def scrape_product(self, listing_id: UUID) -> PoolScrapeResult:
        """Scrape a single listing and save to fact_price (sync Session; pool I/O is async)."""
        listing = self.db.get(FactListing, listing_id)
        if not listing:
            return PoolScrapeResult(success=False, url="", error="listing_not_found")

        now = datetime.now(timezone.utc)
        listing.last_checked_at = now

        mp = self.db.get(DimMarketplace, listing.marketplace_id)
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

        logger.info(
            "pool_scrape start listing_id=%s url=%s",
            listing_id,
            (listing.external_url or "")[:200],
        )
        try:
            result = _run_coro_in_worker(
                self.pool.scrape_product(
                    url=listing.external_url,
                    custom_selectors=custom_selectors if custom_selectors else None,
                    requires_js=requires_js,
                ),
            )
        except Exception as exc:
            logger.exception("pool_scrape exception listing_id=%s", listing_id)
            err_text = f"exception:{exc.__class__.__name__}:{exc!s}"
            result = PoolScrapeResult(
                success=False,
                url=listing.external_url,
                error=err_text[:2000],
                data=None,
                duration_ms=None,
            )

        data = result.data
        last_in_stock = (
            getattr(result, "in_stock", None)
            or getattr(data, "in_stock", None)
            or False
        )
        # Debug: log raw extractor fields (product_name vs title) for fact_price and diagnostics.
        logger.info(
            "EXTRACTED → product_name=%s | title=%s | price=%s | currency=%s | in_stock=%s",
            getattr(data, "product_name", None),
            getattr(data, "title", None),
            getattr(data, "price", None),
            getattr(data, "currency", None),
            last_in_stock,
        )
        is_partial = bool(result.is_partial)

        if not result.success or not data:
            listing.consecutive_errors = (listing.consecutive_errors or 0) + 1
            listing.last_error = result.error or "scrape_failed"
        else:
            # product_name from extractor, or title as fallback when product_name is empty.
            product_name_ok = bool(
                data
                and (
                    getattr(data, "product_name", None)
                    or getattr(data, "title", None)
                ),
            )
            is_partial = bool(result.is_partial) or not product_name_ok
            if not product_name_ok:
                logger.warning(
                    "Missing product_name for %s - partial result",
                    listing.external_url[:80],
                )

            listing.last_price = data.price
            listing.last_currency_code = data.currency[:3] if data.currency else None
            listing.last_in_stock = last_in_stock
            listing.consecutive_errors = 0
            listing.last_error = None

            product = self.db.get(DimProduct, listing.product_id)
            if product:
                pn = getattr(data, "product_name", None)
                tt = getattr(data, "title", None)
                pn_nonempty = bool(pn and str(pn).strip())
                if pn_nonempty:
                    label = str(pn).strip()[:500]
                elif tt and str(tt).strip():
                    label = str(tt).strip()[:500]
                else:
                    label = None
                if label:
                    if not pn_nonempty:
                        product.name = label[:500]
                        product.name_normalized = _normalize_product_name(label)
                    elif _should_replace_placeholder_name(
                        product.name,
                        listing.external_url,
                    ):
                        product.name = label[:500]
                        product.name_normalized = _normalize_product_name(label)
                if data.image_url and not product.image_url:
                    product.image_url = data.image_url

            # fact_price only with product name, positive price, and currency
            should_write_price_snapshot = (
                product_name_ok
                and data.price is not None
                and data.price > 0
                and bool(data.currency)
            )
            if not should_write_price_snapshot:
                if not product_name_ok or not bool(data.currency):
                    logger.info(
                        "fact_price skipped: missing product_name or currency (listing_id=%s)",
                        listing_id,
                    )
            if should_write_price_snapshot:
                date_id = _today_date_id(self.db)
                self.db.execute(
                    delete(FactPrice).where(
                        FactPrice.listing_id == listing.id,
                        FactPrice.date_id == date_id,
                    ),
                )
                prev = _previous_price_snapshot(self.db, listing.id, date_id)
                price_change_pct = None
                if prev is not None and prev > 0:
                    price_change_pct = round((float(data.price) - prev) / prev * 100.0, 4)

                price_record = FactPrice(
                    listing_id=listing.id,
                    date_id=date_id,
                    price=float(data.price),
                    currency_code=data.currency[:3],
                    original_price=float(data.original_price) if data.original_price else None,
                    in_stock=last_in_stock,
                    scraped_at=now,
                    price_change_pct=price_change_pct,
                )
                self.db.add(price_record)
                logger.info(
                    "fact_price write listing_id=%s date_id=%s currency=%s",
                    listing_id,
                    date_id,
                    data.currency[:3] if data.currency else None,
                )
            elif not product_name_ok:
                logger.warning(
                    "Skipping price snapshot (no product title) for %s",
                    listing.external_url[:80],
                )
            elif data.currency is None:
                logger.warning(
                    "Missing currency for %s, skipping price snapshot",
                    listing.external_url[:80],
                )

        log_status = self._determine_log_status(
            result,
            is_partial,
            data=data if result.success else None,
        )
        price_found = None
        if result.success and data and data.price is not None:
            price_found = float(data.price)

        log_entry = ScrapeLog(
            listing_id=listing.id,
            marketplace_id=listing.marketplace_id,
            status=log_status,
            url=listing.external_url,
            price_found=price_found,
            in_stock_found=last_in_stock if (result.success and data) else None,
            duration_ms=result.duration_ms,
            scraper_type=result.scraper_layer,
            error_message=result.error,
            error_category=self._categorize_error(result.error) if result.error else None,
        )
        self.db.add(log_entry)
        logger.info(
            "scrape_logs add listing_id=%s status=%s success=%s",
            listing_id,
            log_status,
            result.success,
        )

        product_name_used = getattr(data, "product_name", None) if data else None
        title = getattr(data, "title", None) if data else None
        price = getattr(data, "price", None) if data else None
        currency = getattr(data, "currency", None) if data else None
        logger.info(
            "FINAL PERSIST: product_name=%s | title=%s | price=%s | currency=%s | in_stock=%s | status=%s",
            product_name_used,
            title,
            price,
            currency,
            last_in_stock,
            log_status,
        )

        try:
            self.db.commit()
        except Exception as exc:
            logger.error(
                "scrape persist rollback listing_id=%s err=%s",
                listing_id,
                exc,
                exc_info=True,
            )
            self.db.rollback()
            return PoolScrapeResult(
                success=False,
                url=listing.external_url,
                data=data,
                error="persist_failed",
            )

        logger.info("pool_scrape done listing_id=%s result_success=%s", listing_id, result.success)
        return result

    def _determine_log_status(
        self,
        result: PoolScrapeResult,
        is_partial: bool = False,
        *,
        data: object | None = None,
        has_title: bool | None = None,
        has_price: bool | None = None,
    ) -> str:
        """Map scrape result to scrape_logs.status CHECK constraint value."""
        if not result.success:
            error = (result.error or "").lower()
            if "fetch_failed" in error:
                return "error"
            if "timeout" in error:
                return "timeout"
            if "blocked" in error or "captcha" in error:
                return "blocked"
            if "price_not_found" in error:
                return "price_not_found"
            return "error"
        payload = data if data is not None else result.data
        if result.success and payload is not None:
            # Unit tests: explicit has_title/has_price without passing data= (legacy API).
            if (
                data is None
                and has_title is not None
                and has_price is not None
            ):
                if not has_title:
                    return "missing_critical_data"
                if has_title and not has_price:
                    return "price_not_found"
            elif data is not None:
                # scrape_product: if product_name exists on payload type but is empty while title
                # exists — missing_critical_data (title-only extractors use title fallback for writes).
                pn_field = _payload_has_product_name_field(payload)
                pn_raw = getattr(payload, "product_name", None)
                pn_ok = bool(pn_raw and str(pn_raw).strip())
                t_raw = getattr(payload, "title", None)
                t_ok = bool(t_raw and str(t_raw).strip())
                if pn_field:
                    if not pn_ok:
                        return "missing_critical_data"
                elif not t_ok:
                    return "missing_critical_data"
                if getattr(payload, "price", None) is None:
                    return "price_not_found"
        if is_partial:
            return "success"
        return "success"

    def _categorize_error(self, error: str) -> str | None:
        """Classify error for scrape_logs.error_category."""
        if not error:
            return None
        lowered = error.lower()
        if "fetch" in lowered or "network" in lowered:
            return "network"
        if "parse" in lowered or "extract" in lowered:
            return "parse"
        if "timeout" in lowered:
            return "network"
        if "blocked" in lowered or "captcha" in lowered:
            return "auth"
        if "rate" in lowered:
            return "rate_limit"
        return "parse"

    def get_stale_products(self, limit: int = 500) -> list[UUID]:
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
        result = self.db.execute(stmt)
        return [r[0] for r in result.all()]

    def recalculate_analytics(self, product_id: UUID) -> None:
        """Hook for downstream analytics refresh (no-op until materialized views)."""
        _ = product_id

    def find_incomplete_products(self, limit: int = 100) -> list[UUID]:
        """Listings missing price or image (enrichment backlog)."""
        stmt = (
            select(FactListing.id)
            .join(DimProduct, FactListing.product_id == DimProduct.id)
            .where(FactListing.is_active.is_(True))
            .where((FactListing.last_price.is_(None)) | (DimProduct.image_url.is_(None)))
            .limit(limit)
        )
        result = self.db.execute(stmt)
        return [r[0] for r in result.all()]
