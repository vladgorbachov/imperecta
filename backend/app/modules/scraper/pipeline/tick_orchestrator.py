"""γ-full orchestrator tick: short, re-enqueuing state-machine step for a
distributed full-pipeline parent job.

Both discovery and scrape are fanned out as one child task per marketplace
(``discover_one_marketplace`` / ``scrape_one_marketplace``). The tick owns
dispatch, parallelism, inline reaping of its own stale children, and progress
metadata for both phases.

State lives entirely in ``scrape_jobs`` — the tick itself is stateless and
re-enqueues itself via Celery ``apply_async(countdown=...)`` until terminal.
A Railway redeploy that kills mid-tick is therefore non-fatal: the next worker
pick picks up the parent metadata + child rows and resumes.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import ScrapeJob
from app.models.dimensions import DimMarketplace
from app.modules.scraper.discovery import DISCOVERY_PER_MARKETPLACE_BUDGET_SECONDS
from app.modules.scraper.pipeline.metadata_store import PipelineMetadataStore

slog = structlog.get_logger(__name__)

# Tick cadence — adaptive: every dispatched tick resets to MIN; idle ticks
# back off ×2 up to MAX so we don't spam the broker while children crunch.
TICK_MIN_SECONDS = 5.0
TICK_MAX_SECONDS = 60.0
TICK_BACKOFF_FACTOR = 2.0

# Per-parent discovery concurrency. Hard cap; intentionally low to keep
# proxy/quota pressure predictable and to avoid blowing the worker pool.
MAX_PARALLEL_DISCOVERY = 2

# Per-parent scrape concurrency for the upcoming O4b fan-out. Mirrors
# MAX_PARALLEL_DISCOVERY's intent. Not yet read by anything; O4a only
# defines it so O4b is a pure tick rewire.
MAX_PARALLEL_SCRAPE = 2

# A pending child whose apply_async was lost (tick crashed between commit and
# dispatch, or broker dropped the message) is re-dispatched after this many
# seconds. Existing row is reused; we never insert a duplicate.
CHILD_PENDING_RECONCILE_SECONDS = 120

# Inline reap of THIS parent's own stale running discovery children. Mirrors
# the global reaper threshold but lives inside the tick so freed slots are
# reused immediately instead of waiting up to ~5 min for the Beat reaper.
CHILD_RUNNING_REAP_SECONDS = DISCOVERY_PER_MARKETPLACE_BUDGET_SECONDS + 120

# Scrape child reap: a running scrape child older than this is presumed
# dead and marked failed. Mirrors discovery reap but sized to the scrape
# child time_limit (scrape_one_marketplace has time_limit=960), not to the
# discovery budget. Margin beyond time_limit so a child finishing right at
# the limit is not preemptively reaped.
SCRAPE_CHILD_RUNNING_REAP_SECONDS = 960 + 120


def _next_backoff(current: float, *, dispatched: bool) -> float:
    """Adaptive countdown for the next tick.

    Pure function for unit-testability. ``dispatched=True`` means the tick made
    forward progress (created/redispatched at least one child) — reset to MIN.
    Idle ticks grow geometrically (×2) but are capped at MAX. A zero/unset
    current value seeds at MIN.
    """
    if dispatched:
        return TICK_MIN_SECONDS
    if current <= 0:
        return TICK_MIN_SECONDS
    return min(current * TICK_BACKOFF_FACTOR, TICK_MAX_SECONDS)


def _reenqueue(parent_job_id: UUID, countdown_s: float) -> None:
    """Schedule the next tick. Import lazily to break the circular task ↔
    orchestrator dependency at module load."""
    from app.modules.scraper.tasks import orchestrator_tick

    orchestrator_tick.apply_async([str(parent_job_id)], countdown=countdown_s)


async def _load_active_marketplace_codes(
    db: AsyncSession, codes_filter: list[str] | None
) -> list[str]:
    stmt = select(DimMarketplace.marketplace_code).where(
        DimMarketplace.is_active.is_(True)
    )
    if codes_filter:
        stmt = stmt.where(DimMarketplace.marketplace_code.in_(codes_filter))
    stmt = stmt.order_by(DimMarketplace.marketplace_code.asc())
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def _count_active_children(db: AsyncSession, parent_id: UUID) -> int:
    """Pending+running discovery children of this parent (uses
    ``idx_scrape_jobs_parent_status``)."""
    result = await db.execute(
        select(func.count(ScrapeJob.id)).where(
            ScrapeJob.parent_job_id == parent_id,
            ScrapeJob.job_type == "discovery",
            ScrapeJob.status.in_(("pending", "running")),
        )
    )
    return int(result.scalar_one() or 0)


async def _create_pending_child(
    db: AsyncSession, parent_id: UUID, marketplace_code: str
) -> UUID | None:
    """Insert a pending discovery child for ``marketplace_code``.

    Caller commits before ``apply_async`` so the worker can never see a phantom
    job_id that the DB rolled back. Returns ``None`` when the marketplace was
    deactivated between queue snapshot and dispatch (silently skipped).
    """
    result = await db.execute(
        select(DimMarketplace).where(
            DimMarketplace.marketplace_code == marketplace_code,
            DimMarketplace.is_active.is_(True),
        )
    )
    marketplace = result.scalar_one_or_none()
    if marketplace is None:
        return None
    job = ScrapeJob(
        job_type="discovery",
        status="pending",
        parent_job_id=parent_id,
        marketplace_id=marketplace.id,
        config={"domain": (marketplace.domain or "").strip()},
    )
    db.add(job)
    await db.flush()
    return job.id


async def _reap_stale_children(db: AsyncSession, parent_id: UUID) -> int:
    """Mark this parent's overrun running discovery children failed.

    Single statement (asyncpg requirement). Commits to free MAX_PARALLEL slots
    for the same tick's dispatch loop. Defense-in-depth: the global Beat
    reaper still catches orphans whose tick is also dead.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=CHILD_RUNNING_REAP_SECONDS)
    result = await db.execute(
        text(
            """
            UPDATE scrape_jobs
            SET status = 'failed',
                completed_at = :now,
                duration_ms = (EXTRACT(
                    EPOCH FROM (:now - COALESCE(started_at, :now))
                )::int) * 1000
            WHERE parent_job_id = :pid
              AND job_type = 'discovery'
              AND status = 'running'
              AND started_at < :cutoff
            RETURNING id
            """
        ),
        {"now": now, "pid": parent_id, "cutoff": cutoff},
    )
    reaped_ids = [row[0] for row in result.all()]
    if reaped_ids:
        await db.commit()
        slog.warning(
            "tick_reaped_stale_children",
            parent_id=str(parent_id),
            count=len(reaped_ids),
            child_ids=[str(cid) for cid in reaped_ids[:20]],
        )
    return len(reaped_ids)


async def _reconcile_pending_children(
    db: AsyncSession, parent_id: UUID
) -> int:
    """Re-dispatch pending children older than the reconcile threshold.

    Their initial ``apply_async`` was lost (tick crash before broker write or
    broker drop). Row is reused — no duplicate insert.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=CHILD_PENDING_RECONCILE_SECONDS)
    result = await db.execute(
        select(ScrapeJob.id).where(
            ScrapeJob.parent_job_id == parent_id,
            ScrapeJob.job_type == "discovery",
            ScrapeJob.status == "pending",
            ScrapeJob.created_at < cutoff,
        )
    )
    ids = [row[0] for row in result.all()]
    if not ids:
        return 0
    from app.modules.scraper.tasks import discover_one_marketplace

    for child_id in ids:
        discover_one_marketplace.apply_async([str(child_id)])
    slog.info(
        "tick_reconciled_pending_children",
        parent_id=str(parent_id),
        count=len(ids),
    )
    return len(ids)


# ---------------------------------------------------------------------------
# Scrape sibling helpers (O4b): mirror the discovery helpers above, scoped to
# job_type='scrape'. Discovery helpers are intentionally untouched so their
# tests stay green.
# ---------------------------------------------------------------------------


async def _count_active_scrape_children(
    db: AsyncSession, parent_id: UUID
) -> int:
    """Pending+running scrape children of this parent (uses
    ``idx_scrape_jobs_parent_status``)."""
    result = await db.execute(
        select(func.count(ScrapeJob.id)).where(
            ScrapeJob.parent_job_id == parent_id,
            ScrapeJob.job_type == "scrape",
            ScrapeJob.status.in_(("pending", "running")),
        )
    )
    return int(result.scalar_one() or 0)


async def _create_pending_scrape_child(
    db: AsyncSession, parent_id: UUID, marketplace_code: str
) -> UUID | None:
    """Insert a pending scrape child for ``marketplace_code``.

    Caller commits before ``apply_async`` so the worker can never see a phantom
    job_id that the DB rolled back. Returns ``None`` when the marketplace was
    deactivated between queue snapshot and dispatch (silently skipped).
    """
    result = await db.execute(
        select(DimMarketplace).where(
            DimMarketplace.marketplace_code == marketplace_code,
            DimMarketplace.is_active.is_(True),
        )
    )
    marketplace = result.scalar_one_or_none()
    if marketplace is None:
        return None
    job = ScrapeJob(
        job_type="scrape",
        status="pending",
        parent_job_id=parent_id,
        marketplace_id=marketplace.id,
        config={"domain": (marketplace.domain or "").strip()},
    )
    db.add(job)
    await db.flush()
    return job.id


async def _reap_stale_scrape_children(
    db: AsyncSession, parent_id: UUID
) -> int:
    """Mark this parent's overrun running scrape children failed.

    Single statement (asyncpg requirement). Commits to free MAX_PARALLEL_SCRAPE
    slots for the same tick's dispatch loop. Cutoff is sized to the scrape
    child time_limit (SCRAPE_CHILD_RUNNING_REAP_SECONDS), not the discovery
    budget.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=SCRAPE_CHILD_RUNNING_REAP_SECONDS)
    result = await db.execute(
        text(
            """
            UPDATE scrape_jobs
            SET status = 'failed',
                completed_at = :now,
                duration_ms = (EXTRACT(
                    EPOCH FROM (:now - COALESCE(started_at, :now))
                )::int) * 1000
            WHERE parent_job_id = :pid
              AND job_type = 'scrape'
              AND status = 'running'
              AND started_at < :cutoff
            RETURNING id
            """
        ),
        {"now": now, "pid": parent_id, "cutoff": cutoff},
    )
    reaped_ids = [row[0] for row in result.all()]
    if reaped_ids:
        await db.commit()
        slog.warning(
            "tick_reaped_stale_scrape_children",
            parent_id=str(parent_id),
            count=len(reaped_ids),
            child_ids=[str(cid) for cid in reaped_ids[:20]],
        )
    return len(reaped_ids)


async def _reconcile_pending_scrape_children(
    db: AsyncSession, parent_id: UUID
) -> int:
    """Re-dispatch pending scrape children older than the reconcile threshold.

    Their initial ``apply_async`` was lost (tick crash before broker write or
    broker drop). Row is reused — no duplicate insert.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=CHILD_PENDING_RECONCILE_SECONDS)
    result = await db.execute(
        select(ScrapeJob.id).where(
            ScrapeJob.parent_job_id == parent_id,
            ScrapeJob.job_type == "scrape",
            ScrapeJob.status == "pending",
            ScrapeJob.created_at < cutoff,
        )
    )
    ids = [row[0] for row in result.all()]
    if not ids:
        return 0
    from app.modules.scraper.tasks import scrape_one_marketplace

    for child_id in ids:
        scrape_one_marketplace.apply_async([str(child_id)])
    slog.info(
        "tick_reconciled_pending_scrape_children",
        parent_id=str(parent_id),
        count=len(ids),
    )
    return len(ids)


async def run_tick(db: AsyncSession, parent_job_id: UUID) -> dict[str, Any]:
    """One short state-machine step for a tick-mode pipeline parent.

    Returns a small status dict (for logging/tests). Side effects:
    - dispatches up to ``MAX_PARALLEL_DISCOVERY`` child tasks per call,
    - reaps stale own children + reconciles lost pending,
    - touches parent metadata (heartbeat + phase/queue/backoff),
    - re-enqueues itself unless terminal (parent not running, complete, or
      unknown_phase — caller logs the latter).
    """
    store = PipelineMetadataStore(db, parent_job_id)
    job, metadata = await store.load()
    if job is None:
        return {"status": "not_found"}
    if job.status != "running":
        # Cancelled, completed, partial, or failed elsewhere → stop the tick
        # loop. No re-enqueue, no dispatch. The parent has a terminal status,
        # so admin UI shows the right thing.
        return {"status": "stopped", "job_status": job.status}

    # Lazy init on first tick — snapshot active marketplaces into the queue so
    # all subsequent decisions are deterministic and don't re-query DimMarketplace
    # on every tick.
    phase = metadata.get("phase")
    if phase is None:
        active_codes = await _load_active_marketplace_codes(
            db, PipelineMetadataStore.marketplace_codes_filter(metadata)
        )
        phase = "discovery"
        metadata["phase"] = phase
        metadata["mp_queue"] = active_codes
        metadata["mp_total"] = len(active_codes)
        metadata["tick_count"] = 0
        metadata["backoff_s"] = TICK_MIN_SECONDS
        metadata["resume_attempts"] = 0

    metadata["tick_count"] = int(metadata.get("tick_count", 0)) + 1

    # Self-reap + reconcile run BEFORE the dispatch loop so freed slots are
    # reused this tick (no extra round-trip).
    await _reap_stale_children(db, parent_job_id)
    reapplied = await _reconcile_pending_children(db, parent_job_id)
    dispatched = reapplied > 0

    if phase == "discovery":
        active = await _count_active_children(db, parent_job_id)
        queue: list[str] = list(metadata.get("mp_queue", []))
        from app.modules.scraper.tasks import discover_one_marketplace

        while active < MAX_PARALLEL_DISCOVERY and queue:
            code = queue.pop(0)
            child_id = await _create_pending_child(
                db, parent_job_id, code
            )
            if child_id is None:
                continue
            await db.commit()
            discover_one_marketplace.apply_async([str(child_id)])
            active += 1
            dispatched = True

        metadata["mp_queue"] = queue
        finished = metadata["mp_total"] - len(queue) - active
        metadata["discovery_marketplace_total"] = metadata["mp_total"]
        metadata["discovery_marketplace_done"] = max(0, finished)

        if not queue and active == 0:
            metadata["phase"] = "scrape"
            metadata["backoff_s"] = TICK_MIN_SECONDS
            await store.touch(job, metadata, stage="scrape")
            _reenqueue(parent_job_id, TICK_MIN_SECONDS)
            return {"status": "phase_advanced", "phase": "scrape"}

        backoff = _next_backoff(
            float(metadata.get("backoff_s", TICK_MIN_SECONDS)),
            dispatched=dispatched,
        )
        metadata["backoff_s"] = backoff
        await store.touch(job, metadata, stage="discovery")
        _reenqueue(parent_job_id, backoff)
        return {
            "status": "ticking",
            "phase": "discovery",
            "queue_left": len(queue),
            "active": active,
            "backoff_s": backoff,
        }

    if phase == "scrape":
        # O4b: per-marketplace scrape fan-out, mirror of the discovery phase.
        # Each scrape child owns a ScrapeJob row (job_type='scrape') and runs
        # the marketplace-scoped sync scrape internally; the tick only does
        # dispatch/reap/reconcile + heartbeat metadata.
        if metadata.get("scrape_queue") is None:
            scrape_codes = await _load_active_marketplace_codes(
                db, PipelineMetadataStore.marketplace_codes_filter(metadata)
            )
            metadata["scrape_queue"] = scrape_codes
            metadata["scrape_total"] = len(scrape_codes)

        await _reap_stale_scrape_children(db, parent_job_id)
        reapplied_s = await _reconcile_pending_scrape_children(db, parent_job_id)
        if reapplied_s > 0:
            dispatched = True

        active = await _count_active_scrape_children(db, parent_job_id)
        queue: list[str] = list(metadata.get("scrape_queue", []))
        from app.modules.scraper.tasks import scrape_one_marketplace

        while active < MAX_PARALLEL_SCRAPE and queue:
            code = queue.pop(0)
            child_id = await _create_pending_scrape_child(
                db, parent_job_id, code
            )
            if child_id is None:
                continue
            await db.commit()
            scrape_one_marketplace.apply_async([str(child_id)])
            active += 1
            dispatched = True

        metadata["scrape_queue"] = queue
        finished = metadata["scrape_total"] - len(queue) - active
        metadata["scrape_marketplace_total"] = metadata["scrape_total"]
        metadata["scrape_marketplace_done"] = max(0, finished)

        if not queue and active == 0:
            metadata["phase"] = "complete"
            metadata["backoff_s"] = TICK_MIN_SECONDS
            await store.touch(job, metadata, stage="persist")
            _reenqueue(parent_job_id, TICK_MIN_SECONDS)
            return {"status": "phase_advanced", "phase": "complete"}

        backoff = _next_backoff(
            float(metadata.get("backoff_s", TICK_MIN_SECONDS)),
            dispatched=dispatched,
        )
        metadata["backoff_s"] = backoff
        await store.touch(job, metadata, stage="scrape")
        _reenqueue(parent_job_id, backoff)
        return {
            "status": "ticking",
            "phase": "scrape",
            "queue_left": len(queue),
            "active": active,
            "backoff_s": backoff,
        }

    if phase == "complete":
        from app.modules.scraper.pipeline.child_aggregation import (
            aggregate_discovery_children,
            aggregate_scrape_children,
            merge_phase_seeds,
        )
        from app.modules.scraper.pipeline.job_completion import (
            complete_pipeline_job,
        )

        discovery_seed = await aggregate_discovery_children(db, parent_job_id)
        scrape_seed = await aggregate_scrape_children(db, parent_job_id)
        per_marketplace = merge_phase_seeds(discovery_seed, scrape_seed)
        hard_error = metadata.get("scrape_error")
        await complete_pipeline_job(
            db,
            job,
            discovery_ms=0,
            scrape_ms=0,
            persist_ms=0,
            per_marketplace_seed=per_marketplace,
            hard_error=hard_error,
        )
        return {"status": "complete", "job_status": job.status}

    # Unknown phase value — fail safe: stop ticking without re-enqueue. The
    # global Beat reaper will eventually mark the parent failed if it stays
    # running too long; the orchestrator will not loop forever in here.
    slog.error(
        "tick_unknown_phase",
        parent_id=str(parent_job_id),
        phase=phase,
    )
    return {"status": "unknown_phase", "phase": phase}
