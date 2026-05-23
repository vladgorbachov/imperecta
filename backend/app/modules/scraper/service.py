"""Global pool scraping: FactListing → FactPrice, DimProduct enrichment."""

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, is_dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, TypeVar
from uuid import UUID

import structlog
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.app_tables import ScrapeLog
from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing, FactPrice
from app.modules.scraper.scraper_pool import PoolScrapeResult, ScraperPool

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)
_CORO_RESULT = TypeVar("_CORO_RESULT")

_SCRAPE_LOG_STATUSES = (
    "success",
    "error",
    "timeout",
    "blocked",
    "captcha",
    "not_found",
    "price_not_found",
    "parse_error",
    "missing_critical_data",
    "technical_error",
)
_MAX_ABS_PRICE_CHANGE_PCT = 9_999.9999


def _run_coro_in_worker(coro: Awaitable[_CORO_RESULT]) -> _CORO_RESULT:
    """Run async pool I/O from sync Celery code, even with an active loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Celery worker may already have a running loop in this thread.
    # Execute coroutine in a dedicated thread to avoid nested-loop RuntimeError.
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="scraper-async-bridge") as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


def _needs_scrape_logs_constraint_repair(exc: Exception) -> bool:
    """Detect legacy DB constraint that does not allow technical_error status."""
    message = str(exc).lower()
    if "scrape_logs" not in message:
        return False
    if "technical_error" not in message:
        return False
    return (
        "scrape_logs_status_check" in message
        or "ck_scrape_logs_status" in message
        or "check constraint" in message
    )


def _needs_scrape_logs_status_column_repair(exc: Exception) -> bool:
    """Detect legacy scrape_logs.status VARCHAR(20) drift."""
    message = str(exc).lower()
    return (
        "stringdatarighttruncation" in message
        and "character varying(20)" in message
    )


def _repair_scrape_logs_status_column(db: Session) -> bool:
    """Widen scrape_logs.status to varchar(50) for current status taxonomy."""
    try:
        db.execute(text("ALTER TABLE scrape_logs ALTER COLUMN status TYPE VARCHAR(50)"))
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


def _repair_scrape_logs_status_constraint(db: Session) -> bool:
    """Repair scrape_logs.status CHECK to allow all supported statuses."""
    allowed = ",".join(f"'{status}'" for status in _SCRAPE_LOG_STATUSES)
    try:
        db.execute(text("ALTER TABLE scrape_logs DROP CONSTRAINT IF EXISTS ck_scrape_logs_status"))
        db.execute(text("ALTER TABLE scrape_logs DROP CONSTRAINT IF EXISTS scrape_logs_status_check"))
        db.execute(
            text(
                "ALTER TABLE scrape_logs "
                "ADD CONSTRAINT ck_scrape_logs_status "
                f"CHECK (status IN ({allowed}))"
            )
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


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


def _compute_price_change_pct(prev_price: float | None, current_price: float) -> float | None:
    """Compute bounded price change percent for Numeric(8,4) column."""
    if prev_price is None or prev_price <= 0:
        return None
    pct = round((float(current_price) - prev_price) / prev_price * 100.0, 4)
    if abs(pct) > _MAX_ABS_PRICE_CHANGE_PCT:
        return None
    return pct


class GlobalScrapeService:
    """Scrape pool listings and persist FactPrice + listing denormalized fields.

    Emits ScrapeLog rows with status/error classification (including technical_error
    paths), applies fact_price quality gates, and resolves dim_date for snapshots.
    """

    def __init__(
        self,
        db: Session,
        scraper_pool: ScraperPool,
        scrape_job_id: UUID | None = None,
    ):
        self.db = db
        self.pool = scraper_pool
        self.scrape_job_id = scrape_job_id

    def _build_scrape_log_entry(
        self,
        *,
        listing: FactListing,
        log_status: str,
        price_found: float | None,
        in_stock_found: bool | None,
        duration_ms: int | None,
        scraper_type: str | None,
        error_message: str | None,
        error_category: str | None,
    ) -> ScrapeLog:
        """Create a fresh ScrapeLog object for safe retry attempts."""
        return ScrapeLog(
            scrape_job_id=self.scrape_job_id,
            listing_id=listing.id,
            marketplace_id=listing.marketplace_id,
            status=log_status,
            url=listing.external_url,
            price_found=price_found,
            in_stock_found=in_stock_found,
            duration_ms=duration_ms,
            scraper_type=scraper_type,
            error_message=error_message,
            error_category=error_category,
        )

    def _persist_scrape_log(
        self,
        *,
        listing: FactListing,
        log_status: str,
        price_found: float | None,
        in_stock_found: bool | None,
        duration_ms: int | None,
        scraper_type: str | None,
        error_message: str | None,
        error_category: str | None,
    ) -> bool:
        """Persist scrape_logs row without risking rollback of listing/price transaction."""

        def _try_commit(status: str) -> bool:
            entry = self._build_scrape_log_entry(
                listing=listing,
                log_status=status,
                price_found=price_found,
                in_stock_found=in_stock_found,
                duration_ms=duration_ms,
                scraper_type=scraper_type,
                error_message=error_message,
                error_category=error_category,
            )
            self.db.add(entry)
            self.db.flush()
            self.db.commit()
            return True

        try:
            return _try_commit(log_status)
        except Exception as exc:
            self.db.rollback()

            if _needs_scrape_logs_constraint_repair(exc) and _repair_scrape_logs_status_constraint(self.db):
                try:
                    return _try_commit(log_status)
                except Exception:
                    self.db.rollback()

            if _needs_scrape_logs_status_column_repair(exc) and _repair_scrape_logs_status_column(self.db):
                try:
                    return _try_commit(log_status)
                except Exception:
                    self.db.rollback()

            # Legacy emergency fallback: keep business data committed even if status taxonomy drifts.
            if log_status != "error":
                try:
                    return _try_commit("error")
                except Exception:
                    self.db.rollback()

            logger.error(
                "scrape log persist failed listing_id=%s err=%s",
                listing.id,
                exc,
                exc_info=True,
            )
            return False

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

        slog.info(
            "pool_scrape_start",
            listing_id=str(listing_id),
            url=(listing.external_url or "")[:200],
        )
        listing.last_error = None
        listing.consecutive_errors = 0
        try:
            result = _run_coro_in_worker(
                self.pool.scrape_product(
                    url=listing.external_url,
                    custom_selectors=custom_selectors if custom_selectors else None,
                    requires_js=requires_js,
                ),
            )
        except Exception as exc:
            slog.exception("pool_scrape_exception", listing_id=str(listing_id))
            err_text = f"exception:{exc.__class__.__name__}:{exc!s}"
            result = PoolScrapeResult(
                success=False,
                url=listing.external_url,
                error=err_text[:2000],
                data=None,
                duration_ms=None,
            )

        data = result.data
        # Legacy cleanup: any successful pool response clears stale error counters.
        if result.success:
            listing.last_error = None
            listing.consecutive_errors = 0

        last_in_stock = (
            getattr(result, "in_stock", None)
            or getattr(data, "in_stock", None)
            or False
        )
        slog.info(
            "EXTRACTED_DATA",
            line="EXTRACTED DATA → product_name/title/price/currency/in_stock",
            product_name=getattr(data, "product_name", None),
            title=getattr(data, "title", None),
            price=getattr(data, "price", None),
            currency=getattr(data, "currency", None),
            in_stock=last_in_stock,
            is_partial=getattr(result, "is_partial", False),
            is_empty=getattr(result, "is_empty", False),
            missing_fields=getattr(result, "missing_fields", []),
        )
        is_partial = bool(result.is_partial)

        if not result.success or not data:
            if not result.success:
                listing.consecutive_errors = (listing.consecutive_errors or 0) + 1
                listing.last_error = result.error or "scrape_failed"
        elif data:
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

            # fact_price: product_name_ok, price > 0, currency present (non-empty string)
            curr_raw = getattr(data, "currency", None)
            currency_ok = curr_raw is not None and str(curr_raw).strip() != ""
            price_ok = data.price is not None and data.price > 0
            should_write_price_snapshot = (
                product_name_ok
                and price_ok
                and currency_ok
            )
            slog.info(
                "PERSISTENCE_GATE",
                line="PERSISTENCE GATE → product_name_ok / price_ok / currency_ok",
                product_name_ok=product_name_ok,
                price_ok=price_ok,
                currency_ok=currency_ok,
                price_raw_text=getattr(data, "price_raw_text", None),
                currency_raw=getattr(data, "currency_raw", None),
            )
            if not should_write_price_snapshot:
                if not product_name_ok or not currency_ok:
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
                price_change_pct = _compute_price_change_pct(prev, float(data.price))
                if prev is not None and prev > 0 and price_change_pct is None:
                    logger.warning(
                        "price_change_pct_out_of_range listing_id=%s prev=%s current=%s",
                        listing_id,
                        prev,
                        float(data.price),
                    )

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
        result.log_status = log_status
        price_found = None
        if result.success and data and data.price is not None:
            price_found = float(data.price)
        in_stock_found = last_in_stock if (result.success and data) else None
        error_category = self._categorize_error(result.error) if result.error else None

        product_name_used = getattr(data, "product_name", None) if data else None
        title = getattr(data, "title", None) if data else None
        price = getattr(data, "price", None) if data else None
        currency = getattr(data, "currency", None) if data else None
        slog.info(
            "FINAL_PERSIST",
            line=(
                f"FINAL PERSIST → listing_id={listing_id} status={log_status} "
                f"price={price!s}"
            ),
            listing_id=str(listing_id),
            product_name=product_name_used,
            title=title,
            price=price,
            currency=currency,
            in_stock=last_in_stock,
            status=log_status,
        )

        try:
            self.db.flush()
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

        slog.info(
            "scrape_logs_queued",
            listing_id=str(listing_id),
            status=log_status,
            success=result.success,
        )
        log_saved = self._persist_scrape_log(
            listing=listing,
            log_status=log_status,
            price_found=price_found,
            in_stock_found=in_stock_found,
            duration_ms=result.duration_ms,
            scraper_type=result.scraper_layer,
            error_message=result.error,
            error_category=error_category,
        )
        if not log_saved:
            slog.error(
                "scrape_log_persist_failed_non_blocking",
                listing_id=str(listing_id),
                status=log_status,
            )

        slog.info(
            "SCRAPE_COMPLETE",
            line="SCRAPE COMPLETE",
            listing_id=str(listing_id),
            status=log_status,
            price=price,
            currency=currency,
            in_stock=last_in_stock,
            success=result.success,
            error=result.error,
            scraper_layer=result.scraper_layer,
            duration_ms=result.duration_ms,
            log_status=log_status,
            is_partial=result.is_partial,
            is_empty=result.is_empty,
        )
        slog.info("pool_scrape_done", listing_id=str(listing_id), result_success=result.success)
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
        """Map scrape result to scrape_logs.status VARCHAR(50) CHECK constraint value."""
        if not result.success:
            error = (result.error or "").lower()
            if error.startswith("exception:"):
                return "technical_error"
            if "price_overflow" in error:
                return "technical_error"
            if "parse_error" in error:
                return "parse_error"
            if "price_not_found" in error:
                return "price_not_found"
            if "not_found" in error:
                return "not_found"
            if "captcha" in error:
                return "captcha"
            if "blocked" in error:
                return "blocked"
            if "timeout" in error:
                return "timeout"
            if "fetch_failed" in error:
                return "error"
            return "error"

        if getattr(result, "is_empty", False):
            return "missing_critical_data"

        payload = data if data is not None else result.data
        fields_missing = list(getattr(result, "missing_fields", []) or [])
        if result.success and payload is not None:
            if "currency" in fields_missing and getattr(payload, "price", None) is not None:
                slog.warning(
                    "price_parsed_no_currency",
                    price=getattr(payload, "price", None),
                    price_raw_text=getattr(payload, "price_raw_text", None),
                    currency_raw=getattr(payload, "currency_raw", None),
                )
                return "missing_critical_data"
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
                curr = getattr(payload, "currency", None)
                if curr is None or not str(curr).strip():
                    slog.warning(
                        "price_parsed_no_currency",
                        price=getattr(payload, "price", None),
                        price_raw_text=getattr(payload, "price_raw_text", None),
                        currency_raw=getattr(payload, "currency_raw", None),
                    )
                    return "missing_critical_data"

        if is_partial:
            return "missing_critical_data"
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
