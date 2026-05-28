"""Finalize full pipeline test jobs (no import from tasks — avoids circular imports)."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.app_tables import ScrapeJob, ScrapeLog
from app.models.dimensions import DimMarketplace
from app.modules.scraper.pipeline.metadata_store import PipelineMetadataStore


def _touch_metadata(
    metadata: dict[str, Any],
    *,
    stage: str | None = None,
) -> dict[str, Any]:
    metadata["last_activity_at"] = datetime.now(UTC).isoformat()
    if stage is not None:
        metadata["current_stage"] = stage
    return metadata


async def finalize_full_pipeline_job(
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
    log_stats = await db.execute(
        select(
            ScrapeLog.marketplace_id,
            func.sum(case((ScrapeLog.status == "success", 1), else_=0)).label("prices_saved"),
            func.sum(case((ScrapeLog.status != "success", 1), else_=0)).label("errors_count"),
        )
        .where(ScrapeLog.scrape_job_id == job.id)
        .group_by(ScrapeLog.marketplace_id)
    )

    stats_by_marketplace = {
        row.marketplace_id: {
            "prices_saved": int(row.prices_saved or 0),
            "errors_count": int(row.errors_count or 0),
        }
        for row in log_stats
    }

    merged: list[dict[str, Any]] = []
    for marketplace_id, seed in per_marketplace_seed.items():
        merged_entry = dict(seed)
        stats = stats_by_marketplace.get(marketplace_id, {})
        merged_entry["prices_saved"] = int(stats.get("prices_saved", merged_entry["prices_saved"]))
        merged_entry["errors_count"] = int(
            merged_entry["errors_count"] + stats.get("errors_count", 0)
        )
        if merged_entry["errors_count"] > 0 and merged_entry["status"] != "running":
            merged_entry["status"] = "failed"
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
            stats = stats_by_marketplace[marketplace_id]
            merged.append(
                {
                    "marketplace_id": str(marketplace_id),
                    "domain": domain_map.get(marketplace_id),
                    "listings_created": 0,
                    "prices_saved": int(stats.get("prices_saved", 0)),
                    "errors_count": int(stats.get("errors_count", 0)),
                    "duration_ms": 0,
                    "status": "failed" if int(stats.get("errors_count", 0)) > 0 else "completed",
                }
            )

    listings_created = int(sum(item["listings_created"] for item in merged))
    prices_saved = int(sum(item["prices_saved"] for item in merged))
    errors_count = int(sum(item["errors_count"] for item in merged))
    total_ms = int(discovery_ms + scrape_ms + persist_ms)

    metadata = PipelineMetadataStore.extract(job.config)
    _touch_metadata(metadata)
    metadata.update(
        {
            "current_stage": "failed" if hard_error else "completed",
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
            },
            "per_marketplace": merged,
        }
    )
    if hard_error:
        metadata["error"] = hard_error[:2000]

    job.completed_at = datetime.now(UTC)
    job.duration_ms = total_ms
    job.total_listings = listings_created
    job.successful = prices_saved
    job.failed = errors_count
    job.status = "failed" if hard_error else "completed"
    job.config = {"metadata": deepcopy(metadata)}
    flag_modified(job, "config")
    await db.commit()
    return metadata
