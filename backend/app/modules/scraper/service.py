"""Pool scrape orchestration + scrape_logs write.

Post-ING1 contract:
    - fetch via ``ScraperPool.scrape_product`` (async, bridged for Celery)
    - delegate gate + FactPrice + DimProduct enrichment + listing denorm to
      ``app.modules.ingestion.IngestionService`` (which commits)
    - write the parser-owned ``scrape_logs`` row via ``_persist_scrape_log``
      (separate commit; non-blocking failure)

Per-shop ``custom_selectors`` read on lines below remains here as the
extractor input contract pending the Phase 5 extractor universality pass
(registry item — do NOT delete in ING1).
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Awaitable, TypeVar
from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import invalidate_sync_session, is_read_only_sql_error
from app.models.app_tables import ScrapeLog
from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing
from app.modules.ingestion.service import (
    IngestionService,
    _normalize_product_name,
    _payload_has_product_name_field,
    _should_replace_placeholder_name,
    _today_date_id,
)
from app.modules.ingestion.gate import MAX_CURRENCY_RAW_LEN
from app.modules.scraper.fetch_backends import backend_id_persisted
from app.modules.scraper.scraper_pool import ListingFetchResult, PoolScrapeResult, ScraperPool

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)
_CORO_RESULT = TypeVar("_CORO_RESULT")

_SCRAPE_LOG_STATUSES = (
    "success",
    "no_change",
    "error",
    "timeout",
    "blocked",
    "captcha",
    "not_found",
    "price_not_found",
    "parse_error",
    "currency_rejected",
    "not_a_product",
    "missing_critical_data",
    "technical_error",
)
# Number of consecutive scrape failures before a listing is deactivated.
# Deactivated listings are excluded from the scrape pool.
LISTING_DEACTIVATE_AFTER_ERRORS = 15

_NON_FAILURE_LOG_STATUSES = frozenset({"success", "no_change"})

_STATUS_ERROR_CATEGORY = {
    "parse_error": "parse",
    "currency_rejected": "data_quality",
    "not_a_product": "data_quality",
    "missing_critical_data": "data_quality",
    "price_not_found": "parse",
    "technical_error": "technical",
    "timeout": "network",
    "blocked": "auth",
    "captcha": "auth",
    "error": "network",
    "not_found": "parse",
}


def _is_failure_log_status(log_status: str) -> bool:
    """True when scrape_logs.status represents a failure or gate rejection."""
    return log_status not in _NON_FAILURE_LOG_STATUSES


def _categorize_from_log_status(log_status: str) -> str | None:
    """Map scrape_logs.status to error_category when result.error is empty."""
    return _STATUS_ERROR_CATEGORY.get(log_status)


def _resolve_scrape_log_diagnostics(
    *,
    result: PoolScrapeResult,
    log_status: str,
    gate_skip_reason: str | None = None,
) -> tuple[str | None, str | None]:
    """Build error_message and error_category for scrape_logs persist."""
    error_message = result.error
    if not error_message:
        if _is_failure_log_status(log_status):
            if gate_skip_reason:
                error_message = f"gate:{gate_skip_reason}"
            else:
                error_message = f"status:{log_status}"
        elif not result.success:
            error_message = f"status:{log_status}"

    if result.error:
        error_category = _categorize_error_text(result.error)
    else:
        error_category = _categorize_from_log_status(log_status)

    return error_message, error_category


def _categorize_error_text(error: str) -> str | None:
    """Classify error text for scrape_logs.error_category."""
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

# Back-compat re-exports so legacy scraper unit tests that monkeypatch /
# import these symbols from this module keep working after ING1 moved them
# to ``app.modules.ingestion``. Canonical ownership is ingestion's; this
# module merely re-exports.
__all__ = [
    "GlobalScrapeService",
    "LISTING_DEACTIVATE_AFTER_ERRORS",
    "MAX_CURRENCY_RAW_LEN",
    "_today_date_id",
    "_normalize_product_name",
    "_should_replace_placeholder_name",
    "_payload_has_product_name_field",
]


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


def _is_read_only_error(exc: BaseException) -> bool:
    """Detect Postgres read-only transaction errors (SQLSTATE 25006)."""
    return is_read_only_sql_error(exc)


def _invalidate_session(db: Session) -> None:
    """Return a broken sync connection to the pool for discard."""
    invalidate_sync_session(db)


def _is_honest_absent_scrape_result(result: PoolScrapeResult) -> bool:
    """Scrape reached an honest no-price / gone verdict (not a write failure)."""
    if result.success:
        return False
    err = (result.error or "").lower()
    if "price_not_found" in err:
        return True
    if "not_found" in err:
        return True
    if "product_gone" in err or "product gone" in err:
        return True
    return False


def _read_only_retriable_result(
    *,
    url: str,
    data: object | None = None,
) -> PoolScrapeResult:
    return PoolScrapeResult(
        success=False,
        url=url,
        data=data,
        error="read_only_retriable",
    )


class GlobalScrapeService:
    """Orchestrate ScraperPool fetch + ingestion + scrape_logs write.

    Post-ING1: ingestion logic (gate + FactPrice + DimProduct enrichment +
    listing denorm) has moved to ``IngestionService``. This class now owns
    only the parser-side concerns: fetch orchestration, consecutive-error
    handling on failed scrape (incl. listing deactivation), scrape_logs row
    construction + commit (separate transaction), and the status classifier.
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

    # Back-compat thin delegate; canonical ownership is IngestionService.
    @staticmethod
    def _should_skip_price_record(
        listing: FactListing,
        new_price: float | None,
        new_currency: str | None,
    ) -> bool:
        return IngestionService._should_skip_price_record(
            listing, new_price, new_currency
        )

    def _persist_listing_housekeeping_or_fail(
        self,
        listing: FactListing,
        *,
        url: str,
        data: object | None = None,
    ) -> PoolScrapeResult | None:
        """Flush+commit listing error/checked state; return a result on failure."""
        try:
            self.db.flush()
            self.db.commit()
        except Exception as exc:
            logger.error(
                "scrape failure-path persist rollback listing_id=%s err=%s",
                listing.id,
                exc,
                exc_info=True,
            )
            self.db.rollback()
            if _is_read_only_error(exc):
                _invalidate_session(self.db)
                return _read_only_retriable_result(url=url, data=data)
            return PoolScrapeResult(
                success=False,
                url=url,
                data=data,
                error="persist_failed",
            )
        return None

    def _build_scrape_log_entry(
        self,
        *,
        listing: FactListing,
        log_status: str,
        price_found: float | None,
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

    def _listing_scrape_context(
        self,
        listing: FactListing,
    ) -> tuple[bool, int, dict[str, str]]:
        """Return requires_js, scrape_tier, and custom_selectors for one listing."""
        mp = self.db.get(DimMarketplace, listing.marketplace_id)
        requires_js = bool(mp.requires_js) if mp else False
        scrape_tier = int(mp.scrape_tier) if mp and mp.scrape_tier is not None else 1
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
        return requires_js, scrape_tier, custom_selectors

    def scrape_listing_from_fetch(
        self,
        listing_id: UUID,
        fetch: ListingFetchResult,
    ) -> PoolScrapeResult | None:
        """Extract + persist after a parallel fetch. None = deadline-skipped (no counters)."""
        if fetch.deadline_skipped:
            return None

        listing = self.db.get(FactListing, listing_id)
        if not listing:
            return PoolScrapeResult(success=False, url="", error="listing_not_found")

        now = datetime.now(timezone.utc)
        requires_js, scrape_tier, custom_selectors = self._listing_scrape_context(listing)

        slog.info(
            "pool_scrape_start",
            listing_id=str(listing_id),
            url=(listing.external_url or "")[:200],
        )
        listing.consecutive_errors = 0
        listing.last_error = None

        if fetch.html:
            result = self.pool.build_scrape_result_from_html(
                fetch.html,
                listing.external_url,
                custom_selectors=custom_selectors if custom_selectors else None,
                used_backend=fetch.used_backend,
                duration_ms=fetch.duration_ms,
                last_error=fetch.last_error,
                scrape_tier=scrape_tier,
                requires_js=requires_js,
            )
        else:
            result = PoolScrapeResult(
                success=False,
                url=listing.external_url,
                error=fetch.last_error,
                data=None,
                fetch_backend=backend_id_persisted(fetch.used_backend),
                duration_ms=fetch.duration_ms,
                is_empty=True,
            )

        return self._persist_scrape_pool_result(
            listing_id,
            listing,
            result,
            now=now,
        )

    def _persist_scrape_pool_result(
        self,
        listing_id: UUID,
        listing: FactListing,
        result: PoolScrapeResult,
        *,
        now: datetime,
    ) -> PoolScrapeResult:
        """Sequential persist path for one PoolScrapeResult (D4 semantics preserved)."""
        data = result.data
        if result.success:
            listing.failure_streak = 0

        is_partial = bool(result.is_partial)
        forced_log_status: str | None = None
        gate_skip_reason: str | None = None

        if not result.success or not data:
            if not result.success:
                listing.consecutive_errors = (listing.consecutive_errors or 0) + 1
                listing.last_error = result.error or "scrape_failed"
                listing.failure_streak = (listing.failure_streak or 0) + 1
                if listing.failure_streak >= LISTING_DEACTIVATE_AFTER_ERRORS:
                    listing.is_active = False
                    logger.warning(
                        "LISTING_DEACTIVATED listing_id=%s failure_streak=%d url=%s",
                        listing_id,
                        listing.failure_streak,
                        listing.external_url,
                    )
            if _is_honest_absent_scrape_result(result):
                listing.last_checked_at = now
            persist_fail = self._persist_listing_housekeeping_or_fail(
                listing,
                url=listing.external_url,
                data=data,
            )
            if persist_fail is not None:
                return persist_fail
        else:
            listing.last_checked_at = now
            product_name_ok = bool(
                getattr(data, "product_name", None)
                or getattr(data, "title", None),
            )
            is_partial = bool(result.is_partial) or not product_name_ok
            if not product_name_ok:
                logger.warning(
                    "Missing product_name for %s - partial result",
                    listing.external_url[:80],
                )

            ing_result = IngestionService(self.db).persist_extracted(
                data=data,
                listing=listing,
                scrape_job_id=self.scrape_job_id,
            )
            forced_log_status = ing_result.log_status
            gate_skip_reason = ing_result.skip_reason

            if ing_result.read_only_failed:
                return _read_only_retriable_result(
                    url=listing.external_url,
                    data=data,
                )
            if ing_result.persist_failed:
                return PoolScrapeResult(
                    success=False,
                    url=listing.external_url,
                    data=data,
                    error="persist_failed",
                )

        if forced_log_status is None:
            log_status = self._determine_log_status(
                result,
                is_partial,
                data=data if result.success else None,
            )
        else:
            log_status = forced_log_status
        result.log_status = log_status
        error_message, error_category = _resolve_scrape_log_diagnostics(
            result=result,
            log_status=log_status,
            gate_skip_reason=gate_skip_reason,
        )
        price_found = None
        if result.success and data and data.price is not None:
            price_found = float(data.price)

        price = getattr(data, "price", None) if data else None
        currency = getattr(data, "currency", None) if data else None

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
            duration_ms=result.duration_ms,
            scraper_type=result.fetch_backend,
            error_message=error_message,
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
            success=result.success,
            error=result.error,
            fetch_backend=result.fetch_backend,
            duration_ms=result.duration_ms,
            log_status=log_status,
            is_partial=result.is_partial,
            is_empty=result.is_empty,
        )
        slog.info("pool_scrape_done", listing_id=str(listing_id), result_success=result.success)
        return result

    def scrape_product(self, listing_id: UUID) -> PoolScrapeResult:
        """Scrape a single listing and persist via IngestionService + scrape_logs."""
        listing = self.db.get(FactListing, listing_id)
        if not listing:
            return PoolScrapeResult(success=False, url="", error="listing_not_found")

        now = datetime.now(timezone.utc)
        requires_js, scrape_tier, custom_selectors = self._listing_scrape_context(listing)

        slog.info(
            "pool_scrape_start",
            listing_id=str(listing_id),
            url=(listing.external_url or "")[:200],
        )
        listing.consecutive_errors = 0
        listing.last_error = None
        try:
            result = _run_coro_in_worker(
                self.pool.scrape_product(
                    url=listing.external_url,
                    custom_selectors=custom_selectors if custom_selectors else None,
                    requires_js=requires_js,
                    scrape_tier=scrape_tier,
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

        return self._persist_scrape_pool_result(
            listing_id,
            listing,
            result,
            now=now,
        )

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
            if "currency_rejected" in error:
                return "currency_rejected"
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
        return _categorize_error_text(error)

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
