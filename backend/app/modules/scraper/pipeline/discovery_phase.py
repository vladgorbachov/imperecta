"""Discovery phase for full pipeline test."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable
from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimMarketplace
from app.modules.scraper.discovery import (
    DISCOVERY_PER_MARKETPLACE_BUDGET_SECONDS,
    SITEMAP_STALE_DAYS,
    SITEMAP_TIMEOUT_COOLDOWN_HOURS,
    DiscoveryCrawler,
)
from app.modules.scraper.pipeline.activity_pulse import discovery_activity_callback
from app.modules.scraper.pipeline.cancellation import is_pipeline_job_cancelled
from app.modules.scraper.pipeline.metadata_store import PipelineMetadataStore
from app.modules.scraper.scraper_pool import ScraperPool

slog = structlog.get_logger(__name__)

ProgressCallback = Callable[[], Awaitable[None]]


async def run_discovery_phase(
    db: AsyncSession,
    *,
    parent_job_id: UUID,
    marketplace_codes: list[str] | None,
    on_marketplace_done: ProgressCallback | None = None,
) -> tuple[dict[UUID, dict[str, Any]], list[str]]:
    """
    Discover product URLs for active marketplaces (optional code filter).

    Returns per-marketplace seed stats and collected error strings.
    """
    query = select(DimMarketplace).where(DimMarketplace.is_active.is_(True))
    if marketplace_codes:
        query = query.where(DimMarketplace.marketplace_code.in_(marketplace_codes))
    query = query.order_by(DimMarketplace.marketplace_code.asc())
    result = await db.execute(query)
    marketplaces = list(result.scalars().all())

    store = PipelineMetadataStore(db, parent_job_id)
    job, metadata = await store.load()
    if job is not None:
        metadata["discovery_marketplace_total"] = len(marketplaces)
        metadata["discovery_marketplace_done"] = 0
        metadata["discovery_current_domain"] = None
        await store.touch(job, metadata, stage="discovery")

    async def _on_discovery_activity(line: str) -> None:
        await discovery_activity_callback(db, parent_job_id, line)

    crawler = DiscoveryCrawler(db, ScraperPool(), on_activity=_on_discovery_activity)
    errors: list[str] = []
    per_marketplace: dict[UUID, dict[str, Any]] = {}

    for index, marketplace in enumerate(marketplaces):
        if await is_pipeline_job_cancelled(db, parent_job_id):
            slog.info(
                "discovery_phase_aborted_job_not_running",
                parent_job_id=str(parent_job_id),
                marketplace_code=marketplace.marketplace_code,
            )
            errors.append("pipeline_job_cancelled")
            break

        job, metadata = await store.load()
        if job is not None:
            metadata["discovery_current_domain"] = marketplace.domain
            metadata["discovery_marketplace_done"] = index
            await store.touch(job, metadata, stage="discovery")

        started = time.perf_counter()
        try:
            discovered = await asyncio.wait_for(
                crawler.discover(marketplace),
                timeout=DISCOVERY_PER_MARKETPLACE_BUDGET_SECONDS,
            )
            per_marketplace[marketplace.id] = {
                "marketplace_id": str(marketplace.id),
                "domain": marketplace.domain,
                "marketplace_code": marketplace.marketplace_code,
                "listings_created": int(discovered.persisted_listings),
                "prices_saved": 0,
                "errors_count": int(len(discovered.errors)),
                "duration_ms": int(
                    (discovered.completed_at - discovered.started_at).total_seconds() * 1000
                )
                if discovered.completed_at
                else int((time.perf_counter() - started) * 1000),
                "status": "failed" if discovered.status == "error" else "completed",
            }
            errors.extend(discovered.errors)
        except asyncio.TimeoutError:
            # Circuit breaker (Level 3): per-marketplace discovery budget exceeded.
            # crawler.discover() was cancelled mid-flight via CancelledError, so
            # we record the timeout_skipped state ourselves from the caller side
            # and continue with the next marketplace.
            slog.warning(
                "discovery_marketplace_skipped",
                marketplace_id=str(marketplace.id),
                marketplace_code=marketplace.marketplace_code,
                reason="timeout_budget",
                budget_s=DISCOVERY_PER_MARKETPLACE_BUDGET_SECONDS,
            )
            errors.append(f"marketplace_{marketplace.id}_timeout")
            now = datetime.now(tz=timezone.utc)
            # Mark orphaned inner discovery job(s) for this marketplace as failed.
            # asyncio.wait_for cancels DiscoveryCrawler.discover() mid-flight via
            # CancelledError, so the finalization block inside discover() that
            # would otherwise set status='completed'/'failed' never runs. The
            # inner ScrapeJob created at the start of discover() therefore stays
            # in status='running' indefinitely. Reap it here from the caller side
            # while we still hold the outer session — this UPDATE rides on the
            # same transaction as the marketplace status update below.
            await db.execute(
                text(
                    """
                    UPDATE scrape_jobs
                    SET status = 'failed',
                        completed_at = :now,
                        duration_ms = EXTRACT(EPOCH FROM (:now - started_at))::int * 1000
                    WHERE job_type = 'discovery'
                      AND marketplace_id = :mp_id
                      AND status = 'running'
                    """
                ),
                {"now": now, "mp_id": marketplace.id},
            )
            marketplace.last_discovery_status = "timeout_skipped"
            marketplace.last_discovery_at = now
            # Apply 24-hour cooldown to sitemap retry (same rationale as
            # SITEMAP_TIMEOUT_COOLDOWN_HOURS in _phase0_sitemap_harvest).
            retry_offset = timedelta(
                days=SITEMAP_STALE_DAYS,
                hours=-SITEMAP_TIMEOUT_COOLDOWN_HOURS,
            )
            marketplace.last_sitemap_harvest_at = now - retry_offset
            try:
                await db.commit()
            except Exception:
                await db.rollback()
                slog.exception(
                    "discovery_marketplace_skipped_commit_failed",
                    marketplace_id=str(marketplace.id),
                )
            per_marketplace[marketplace.id] = {
                "marketplace_id": str(marketplace.id),
                "domain": marketplace.domain,
                "marketplace_code": marketplace.marketplace_code,
                "listings_created": 0,
                "prices_saved": 0,
                "errors_count": 1,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "status": "timeout_skipped",
            }
        except Exception as exc:
            slog.exception(
                "full_pipeline_discovery_failed",
                marketplace_id=str(marketplace.id),
                error=str(exc),
            )
            errors.append(str(exc))
            per_marketplace[marketplace.id] = {
                "marketplace_id": str(marketplace.id),
                "domain": marketplace.domain,
                "marketplace_code": marketplace.marketplace_code,
                "listings_created": 0,
                "prices_saved": 0,
                "errors_count": 1,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "status": "failed",
            }

        job, metadata = await store.load()
        if job is not None:
            metadata["discovery_marketplace_done"] = index + 1
            metadata["per_marketplace"] = list(per_marketplace.values())
            summary = metadata.setdefault("summary", {})
            if isinstance(summary, dict):
                summary["listings_created"] = int(
                    sum(item.get("listings_created", 0) for item in per_marketplace.values())
                )
            await store.touch(job, metadata, stage="discovery")

        if on_marketplace_done is not None:
            await on_marketplace_done()

    job, metadata = await store.load()
    if job is not None:
        metadata["discovery_current_domain"] = None
        metadata["per_marketplace"] = list(per_marketplace.values())
        await store.touch(job, metadata, stage="discovery")

    return per_marketplace, errors
