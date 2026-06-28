"""Universal orphan-job reaper.

Runs periodically on Celery Beat and marks `scrape_jobs` rows that are stuck
in `status='running'` past a per-type liveness threshold as `status='failed'`.

Why this exists: Railway redeploys SIGTERM the worker process, so any
in-flight discovery / scrape / pipeline job left mid-finalize stays `running`
forever. The tick orchestrator's in-process reap (tick_orchestrator._reap_*)
cannot reap its own process when the worker dies mid-tick. This task runs
externally from Beat and handles that case.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.models.app_tables import ScrapeJob
from app.modules.persist.meta_write import build_scrape_job_failed_fields, write_meta_async
from app.workers.celery_app import celery_app

slog = structlog.get_logger(__name__)


_DISCOVERY_BUDGET_SECONDS = 900
REAPER_DISCOVERY_GRACE_SECONDS = 300
REAPER_DISCOVERY_MAX_RUNTIME_SECONDS = (
    _DISCOVERY_BUDGET_SECONDS + REAPER_DISCOVERY_GRACE_SECONDS
)
REAPER_PIPELINE_HEARTBEAT_STALE_SECONDS = 600
WATCHDOG_REVIVE_FLOOR_SECONDS = 120
REAPER_DEFAULT_MAX_RUNTIME_SECONDS = 3600
_PIPELINE_JOB_TYPE = "full_pipeline_test"


def _run_async(coro):
    """Run an async coroutine from a sync Celery task safely.

    Local copy of the Pattern-A bridge used in `app.modules.scraper.tasks`.
    Defined locally so importing this module does not pull Playwright/httpx
    and the rest of the scraper stack into the worker process.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="reaper-async-bridge") as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


def _make_session_factory() -> tuple:
    """Build a fresh async engine + sessionmaker per task invocation.

    Mirrors the Pattern-A factory in `app.modules.scraper.tasks`. The caller
    MUST `await engine.dispose()` in a `finally` block to avoid leaking the
    asyncpg connection pool when the Celery task returns.
    """
    settings = Settings()
    engine = create_async_engine(
        str(settings.database_url),
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    return engine, factory


def _should_reap_job(
    *,
    job_type: str,
    status: str,
    started_at: datetime | None,
    last_activity_at: datetime | None,
    pipeline_job_type: str,
    now: datetime,
) -> tuple[bool, int]:
    """Pure liveness decision for a single job row.

    Returns `(should_reap, age_seconds)`. `age_seconds` is 0 when the job is
    not running or has no reference timestamp; otherwise it is the elapsed
    time since the relevant liveness signal.
    """
    if status != "running":
        return False, 0
    if job_type == pipeline_job_type:
        ref = last_activity_at or started_at
        if ref is None:
            return False, 0
        age = int((now - ref).total_seconds())
        return age > REAPER_PIPELINE_HEARTBEAT_STALE_SECONDS, age
    if started_at is None:
        return False, 0
    age = int((now - started_at).total_seconds())
    if job_type == "discovery":
        return age > REAPER_DISCOVERY_MAX_RUNTIME_SECONDS, age
    return age > REAPER_DEFAULT_MAX_RUNTIME_SECONDS, age


def _child_liveness_ref(
    *,
    started_at: datetime | None,
    config: dict | None,
) -> datetime | None:
    """Best-effort freshness timestamp for a child job row."""
    cfg = config if isinstance(config, dict) else {}
    metadata = cfg.get("metadata", {}) if isinstance(cfg, dict) else {}
    raw_la = metadata.get("last_activity_at") if isinstance(metadata, dict) else None
    if isinstance(raw_la, str):
        try:
            return datetime.fromisoformat(raw_la)
        except ValueError:
            pass
    return started_at


async def _parent_has_live_child(
    db: AsyncSession,
    parent_id: UUID,
    *,
    now: datetime,
    stale_seconds: int,
) -> bool:
    """True when a pending/running child has a fresh liveness signal."""
    result = await db.execute(
        select(
            ScrapeJob.started_at,
            ScrapeJob.config,
        ).where(
            ScrapeJob.parent_job_id == parent_id,
            ScrapeJob.job_type.in_(("scrape", "discovery")),
            ScrapeJob.status.in_(("pending", "running")),
        )
    )
    for started_at, config in result.all():
        ref = _child_liveness_ref(started_at=started_at, config=config)
        if ref is None:
            continue
        age = int((now - ref).total_seconds())
        if age <= stale_seconds:
            return True
    return False


def _should_revive_pipeline_tick(age_s: int) -> bool:
    """True when a running pipeline parent's heartbeat is stale enough to
    revive but not yet old enough for the reaper to own."""
    return (
        WATCHDOG_REVIVE_FLOOR_SECONDS < age_s < REAPER_PIPELINE_HEARTBEAT_STALE_SECONDS
    )


def _pipeline_heartbeat_age(
    *,
    started_at: datetime | None,
    last_activity_at: datetime | None,
    now: datetime,
) -> int | None:
    """Elapsed seconds since the pipeline parent's liveness signal."""
    ref = last_activity_at or started_at
    if ref is None:
        return None
    return int((now - ref).total_seconds())


async def _revive_stalled_pipeline_ticks_async() -> dict[str, int]:
    """Re-enqueue orchestrator_tick for running pipeline parents with a
    stalled-but-not-yet-reaped heartbeat. Does not mutate job status."""
    now = datetime.now(tz=timezone.utc)
    engine, session_factory = _make_session_factory()
    revived = 0
    try:
        async with session_factory() as db:
            result = await db.execute(
                select(
                    ScrapeJob.id,
                    ScrapeJob.started_at,
                    ScrapeJob.config,
                ).where(
                    ScrapeJob.status == "running",
                    ScrapeJob.job_type == _PIPELINE_JOB_TYPE,
                )
            )
            rows = result.all()
            from app.modules.scraper.tasks import orchestrator_tick

            for row in rows:
                cfg = row.config if isinstance(row.config, dict) else {}
                metadata = cfg.get("metadata", {}) if isinstance(cfg, dict) else {}
                raw_la = (
                    metadata.get("last_activity_at")
                    if isinstance(metadata, dict)
                    else None
                )
                last_activity_at: datetime | None = None
                if isinstance(raw_la, str):
                    try:
                        last_activity_at = datetime.fromisoformat(raw_la)
                    except ValueError:
                        last_activity_at = None
                age = _pipeline_heartbeat_age(
                    started_at=row.started_at,
                    last_activity_at=last_activity_at,
                    now=now,
                )
                if age is None or not _should_revive_pipeline_tick(age):
                    continue
                orchestrator_tick.apply_async([str(row.id)])
                revived += 1
                slog.info(
                    "pipeline_tick_revived",
                    parent_job_id=str(row.id),
                    age_s=age,
                )
            slog.info(
                "pipeline_tick_watchdog_done",
                scanned=len(rows),
                revived=revived,
            )
            return {"scanned": len(rows), "revived": revived}
    finally:
        await engine.dispose()


async def _reap_orphan_jobs_async() -> dict[str, int]:
    """Mark stale `status='running'` jobs as failed.

    Idempotent: an immediate re-run reaps 0 because the previous invocation
    already flipped them to `status='failed'`. The single UPDATE uses
    `AND status='running'` to handle the SELECT→UPDATE race when a job
    finalizes between the two statements.
    """
    now = datetime.now(tz=timezone.utc)
    engine, session_factory = _make_session_factory()
    try:
        async with session_factory() as db:
            result = await db.execute(
                select(
                    ScrapeJob.id,
                    ScrapeJob.job_type,
                    ScrapeJob.status,
                    ScrapeJob.started_at,
                    ScrapeJob.config,
                ).where(ScrapeJob.status == "running")
            )
            rows = result.all()

            reap_targets: list[tuple[UUID, datetime | None]] = []
            for row in rows:
                cfg = row.config if isinstance(row.config, dict) else {}
                metadata = cfg.get("metadata", {}) if isinstance(cfg, dict) else {}
                raw_la = (
                    metadata.get("last_activity_at")
                    if isinstance(metadata, dict)
                    else None
                )
                last_activity_at: datetime | None = None
                if isinstance(raw_la, str):
                    try:
                        last_activity_at = datetime.fromisoformat(raw_la)
                    except ValueError:
                        last_activity_at = None
                should, age = _should_reap_job(
                    job_type=row.job_type,
                    status=row.status,
                    started_at=row.started_at,
                    last_activity_at=last_activity_at,
                    pipeline_job_type=_PIPELINE_JOB_TYPE,
                    now=now,
                )
                if should:
                    if (
                        row.job_type == _PIPELINE_JOB_TYPE
                        and await _parent_has_live_child(
                            db,
                            row.id,
                            now=now,
                            stale_seconds=REAPER_PIPELINE_HEARTBEAT_STALE_SECONDS,
                        )
                    ):
                        slog.info(
                            "reaper_sparing_parent_with_live_child",
                            job_id=str(row.id),
                            age_s=age,
                        )
                        continue
                    reap_targets.append((row.id, row.started_at))
                    slog.warning(
                        "reaper_marking_orphan",
                        job_id=str(row.id),
                        job_type=row.job_type,
                        age_s=age,
                    )

            reaped_count = 0
            if reap_targets:
                try:
                    for job_id, started_at in reap_targets:
                        meta_result = await write_meta_async(
                            table="scrape_jobs",
                            operation="update",
                            fields=build_scrape_job_failed_fields(
                                id=job_id,
                                started_at=started_at,
                                completed_at=now,
                            ),
                            reject_source="reaper_orphan",
                        )
                        if meta_result.ok and not meta_result.no_target:
                            reaped_count += 1
                except Exception:
                    slog.exception(
                        "reaper_update_failed", attempted=len(reap_targets)
                    )
                    raise

            slog.info("reaper_done", scanned=len(rows), reaped=reaped_count)
            return {"scanned": len(rows), "reaped": reaped_count}
    finally:
        await engine.dispose()


@celery_app.task(
    name="app.workers.reaper_tasks.reap_orphan_jobs",
    soft_time_limit=60,
    time_limit=90,
)
def reap_orphan_jobs() -> dict[str, int]:
    """Celery entrypoint: run the async reaper with a hard 90s ceiling."""
    return _run_async(_reap_orphan_jobs_async())


@celery_app.task(
    name="app.workers.reaper_tasks.revive_stalled_pipeline_ticks",
    soft_time_limit=60,
    time_limit=90,
)
def revive_stalled_pipeline_ticks() -> dict[str, int]:
    """Celery Beat entrypoint: revive stalled pipeline tick chains."""
    return _run_async(_revive_stalled_pipeline_ticks_async())
