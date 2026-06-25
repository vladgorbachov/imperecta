"""Complete full-pipeline scrape jobs (isolated from tasks to avoid circular imports)."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import ScrapeJob, ScrapeLog
from app.models.dimensions import DimMarketplace
from app.modules.persist.meta_write import build_scrape_job_fields, write_meta_async
from app.modules.scraper.pipeline.metadata_store import PipelineMetadataStore
from app.modules.scraper.pipeline.outcome_buckets import (
    BUCKET_FAILED,
    BUCKET_FILTERED,
    BUCKET_SUCCESSFUL,
    BUCKET_UNCHANGED,
    aggregate_marketplace_log_rows,
    empty_outcome_buckets,
    sum_buckets_across_marketplaces,
)


def _touch_metadata(
    metadata: dict[str, Any],
    *,
    stage: str | None = None,
) -> dict[str, Any]:
    metadata["last_activity_at"] = datetime.now(UTC).isoformat()
    if stage is not None:
        metadata["current_stage"] = stage
    return metadata


def decide_parent_status(
    seed_statuses: list[str], hard_error: str | None
) -> str:
    """Derive the parent ScrapeJob status from per-marketplace SEED verdicts.

    Pure function (no I/O), unit-testable. Rules (in order):
    - Any ``hard_error`` short-circuits to ``"failed"``.
    - Empty seed list (no marketplaces touched at all) -> ``"failed"`` —
      treated as an anomaly, never silently ``"completed"``.
    - All children ``"completed"``                       -> ``"completed"``.
    - All children non-``"completed"`` (>=1)             -> ``"failed"``.
    - Mixed (>=1 completed AND >=1 non-completed)        -> ``"partial"``.
    """
    if hard_error:
        return "failed"
    if not seed_statuses:
        return "failed"
    completed_n = sum(1 for s in seed_statuses if s == "completed")
    noncompleted_n = len(seed_statuses) - completed_n
    if noncompleted_n == 0:
        return "completed"
    if completed_n == 0:
        return "failed"
    return "partial"


async def complete_pipeline_job(
    db: AsyncSession,
    job: ScrapeJob,
    *,
    discovery_ms: int,
    scrape_ms: int,
    persist_ms: int,
    per_marketplace_seed: dict[UUID, dict[str, Any]],
    hard_error: str | None = None,
) -> dict[str, Any]:
    """Merge discovery/scrape stats into job metadata and mark completed/failed."""
    child_ids_result = await db.execute(
        select(ScrapeJob.id).where(
            ScrapeJob.parent_job_id == job.id,
            ScrapeJob.job_type == "scrape",
        )
    )
    child_scrape_ids = [row[0] for row in child_ids_result.all()]

    log_stats_query = select(
        ScrapeLog.marketplace_id,
        ScrapeLog.status,
        func.count().label("count"),
    ).group_by(ScrapeLog.marketplace_id, ScrapeLog.status)

    if child_scrape_ids:
        log_stats_query = log_stats_query.where(
            ScrapeLog.scrape_job_id.in_(child_scrape_ids)
        )
    else:
        log_stats_query = log_stats_query.where(ScrapeLog.scrape_job_id.is_(None))

    log_stats = await db.execute(log_stats_query)
    stats_by_marketplace = aggregate_marketplace_log_rows(
        list(log_stats),
        job_id=job.id,
    )

    merged: list[dict[str, Any]] = []
    for marketplace_id, seed in per_marketplace_seed.items():
        merged_entry = dict(seed)
        buckets = stats_by_marketplace.get(marketplace_id, empty_outcome_buckets())
        discovery_errors = int(merged_entry.get("errors_count", 0))
        merged_entry[BUCKET_SUCCESSFUL] = int(buckets[BUCKET_SUCCESSFUL])
        merged_entry[BUCKET_UNCHANGED] = int(buckets[BUCKET_UNCHANGED])
        merged_entry[BUCKET_FILTERED] = int(buckets[BUCKET_FILTERED])
        merged_entry[BUCKET_FAILED] = int(buckets[BUCKET_FAILED])
        merged_entry["prices_saved"] = int(buckets[BUCKET_SUCCESSFUL])
        merged_entry["errors_count"] = discovery_errors + int(buckets[BUCKET_FAILED])
        merged.append(merged_entry)

    missing_marketplace_ids = set(stats_by_marketplace) - set(per_marketplace_seed)
    if missing_marketplace_ids:
        domains_result = await db.execute(
            select(DimMarketplace.id, DimMarketplace.domain).where(
                DimMarketplace.id.in_(missing_marketplace_ids)
            )
        )
        domain_map = {row.id: row.domain for row in domains_result}
        for marketplace_id in missing_marketplace_ids:
            buckets = stats_by_marketplace[marketplace_id]
            merged.append(
                {
                    "marketplace_id": str(marketplace_id),
                    "domain": domain_map.get(marketplace_id),
                    "listings_created": 0,
                    "prices_saved": int(buckets[BUCKET_SUCCESSFUL]),
                    "errors_count": int(buckets[BUCKET_FAILED]),
                    BUCKET_SUCCESSFUL: int(buckets[BUCKET_SUCCESSFUL]),
                    BUCKET_UNCHANGED: int(buckets[BUCKET_UNCHANGED]),
                    BUCKET_FILTERED: int(buckets[BUCKET_FILTERED]),
                    BUCKET_FAILED: int(buckets[BUCKET_FAILED]),
                    "duration_ms": 0,
                    "status": "failed" if int(buckets[BUCKET_FAILED]) > 0 else "completed",
                }
            )

    listings_created = int(sum(item["listings_created"] for item in merged))
    run_buckets = sum_buckets_across_marketplaces(stats_by_marketplace)
    prices_saved = int(run_buckets[BUCKET_SUCCESSFUL])
    scrape_failed = int(run_buckets[BUCKET_FAILED])
    errors_count = int(sum(item["errors_count"] for item in merged))
    total_ms = int(discovery_ms + scrape_ms + persist_ms)

    parent_status = decide_parent_status(
        [item["status"] for item in merged], hard_error
    )

    metadata = PipelineMetadataStore.extract(job.config)
    _touch_metadata(metadata)
    metadata.update(
        {
            "current_stage": parent_status,
            "timings": {
                "discovery_ms": int(discovery_ms),
                "scrape_ms": int(scrape_ms),
                "persist_ms": int(persist_ms),
                "total_ms": int(total_ms),
            },
            "summary": {
                "listings_created": listings_created,
                "prices_saved": prices_saved,
                "errors_count": errors_count,
                BUCKET_SUCCESSFUL: int(run_buckets[BUCKET_SUCCESSFUL]),
                BUCKET_UNCHANGED: int(run_buckets[BUCKET_UNCHANGED]),
                BUCKET_FILTERED: int(run_buckets[BUCKET_FILTERED]),
                BUCKET_FAILED: scrape_failed,
                "total": int(run_buckets["total"]),
            },
            "per_marketplace": merged,
        }
    )
    if hard_error:
        metadata["error"] = hard_error[:2000]

    await write_meta_async(
        table="scrape_jobs",
        operation="update",
        fields=build_scrape_job_fields(
            id=job.id,
            status=parent_status,
            completed_at=datetime.now(UTC),
            duration_ms=total_ms,
            total_listings=listings_created,
            successful=prices_saved,
            failed=scrape_failed,
            config={"metadata": deepcopy(metadata)},
        ),
        reject_source="pipeline_completion",
    )
    return metadata
