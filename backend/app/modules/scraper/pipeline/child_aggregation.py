"""Aggregate child discovery ScrapeJobs into the per-marketplace seed shape
that complete_pipeline_job already consumes.

Used by the orchestrator tick (O3); kept isolated and pure (no I/O besides a
single SELECT) for testability. Status passthrough mirrors the 019 status
model — `partial` is a first-class terminal value alongside completed/failed.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import ScrapeJob


async def aggregate_discovery_children(
    db: AsyncSession, parent_job_id: UUID
) -> dict[UUID, dict[str, Any]]:
    """Return ``{marketplace_id: per_marketplace_dict}`` for all child
    discovery jobs of the given parent.

    Each value matches the shape ``complete_pipeline_job`` expects:
    ``marketplace_id`` (str), ``domain`` (from child's config), ``status``
    (child's own status), ``listings_created`` (= ``job.successful``),
    ``prices_saved`` (0; scrape phase fills it), ``errors_count``
    (= ``job.failed``), ``duration_ms``.
    """
    result = await db.execute(
        select(ScrapeJob).where(
            ScrapeJob.parent_job_id == parent_job_id,
            ScrapeJob.job_type == "discovery",
        )
    )
    children = result.scalars().all()
    per_marketplace: dict[UUID, dict[str, Any]] = {}
    for child in children:
        cfg = child.config if isinstance(child.config, dict) else {}
        per_marketplace[child.marketplace_id] = {
            "marketplace_id": str(child.marketplace_id),
            "domain": cfg.get("domain"),
            "listings_created": int(child.successful or 0),
            "prices_saved": 0,
            "errors_count": int(child.failed or 0),
            "duration_ms": int(child.duration_ms or 0),
            "status": child.status,
        }
    return per_marketplace
