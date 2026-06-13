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


async def aggregate_scrape_children(
    db: AsyncSession, parent_job_id: UUID
) -> dict[UUID, dict[str, Any]]:
    """Return ``{marketplace_id: per_marketplace_dict}`` for all child SCRAPE
    jobs of the given parent.

    Mirrors :func:`aggregate_discovery_children` but for ``job_type='scrape'``.
    Scrape children create no listings (``listings_created=0``);
    ``prices_saved=0`` here — :func:`complete_pipeline_job` fills it from the
    ScrapeLog aggregation. ``status`` passes through the child's own
    (partial-aware) terminal status.
    """
    result = await db.execute(
        select(ScrapeJob).where(
            ScrapeJob.parent_job_id == parent_job_id,
            ScrapeJob.job_type == "scrape",
        )
    )
    children = result.scalars().all()
    per_marketplace: dict[UUID, dict[str, Any]] = {}
    for child in children:
        cfg = child.config if isinstance(child.config, dict) else {}
        per_marketplace[child.marketplace_id] = {
            "marketplace_id": str(child.marketplace_id),
            "domain": cfg.get("domain"),
            "listings_created": 0,
            "prices_saved": 0,
            "errors_count": int(child.failed or 0),
            "duration_ms": int(child.duration_ms or 0),
            "status": child.status,
        }
    return per_marketplace


def merge_phase_seeds(
    discovery_seed: dict[UUID, dict[str, Any]],
    scrape_seed: dict[UUID, dict[str, Any]],
) -> dict[UUID, dict[str, Any]]:
    """Merge per-marketplace discovery + scrape seeds by ``marketplace_id``.

    Pure function (no I/O), unit-testable. Rules:
    - When BOTH seeds carry the same marketplace: scrape is the terminal phase,
      so its status wins; ``errors_count`` is the sum across phases; discovery's
      ``listings_created`` / ``duration_ms`` / ``domain`` are kept.
    - When only one seed carries the marketplace: that row is carried through
      verbatim (scrape never reached a discovery-only MP, or vice versa).
    - ``prices_saved`` stays 0 here; :func:`complete_pipeline_job` fills it
      from the ScrapeLog aggregation.
    """
    merged: dict[UUID, dict[str, Any]] = {}
    all_ids = set(discovery_seed) | set(scrape_seed)
    for mp_id in all_ids:
        d = discovery_seed.get(mp_id)
        s = scrape_seed.get(mp_id)
        base = dict(d) if d else dict(s)  # type: ignore[arg-type]
        if d and s:
            base["status"] = s["status"]
            base["errors_count"] = int(d["errors_count"]) + int(s["errors_count"])
        merged[mp_id] = base
    return merged
