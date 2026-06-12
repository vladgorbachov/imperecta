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

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.models.app_tables import ScrapeJob
from app.workers.celery_app import celery_app

slog = structlog.get_logger(__name__)


_DISCOVERY_BUDGET_SECONDS = 900
REAPER_DISCOVERY_GRACE_SECONDS = 300
REAPER_DISCOVERY_MAX_RUNTIME_SECONDS = (
    _DISCOVERY_BUDGET_SECONDS + REAPER_DISCOVERY_GRACE_SECONDS
)
REAPER_PIPELINE_HEARTBEAT_STALE_SECONDS = 600
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

            reap_ids: list = []
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
                    reap_ids.append(row.id)
                    slog.warning(
                        "reaper_marking_orphan",
                        job_id=str(row.id),
                        job_type=row.job_type,
                        age_s=age,
                    )

            if reap_ids:
                try:
                    await db.execute(
                        text(
                            """
                            UPDATE scrape_jobs
                            SET status = 'failed',
                                completed_at = :now,
                                duration_ms = EXTRACT(
                                    EPOCH FROM (:now - COALESCE(started_at, :now))
                                )::int * 1000
                            WHERE id = ANY(:ids) AND status = 'running'
                            """
                        ),
                        {"now": now, "ids": reap_ids},
                    )
                    await db.commit()
                except Exception:
                    await db.rollback()
                    slog.exception(
                        "reaper_update_failed", attempted=len(reap_ids)
                    )
                    raise

            slog.info("reaper_done", scanned=len(rows), reaped=len(reap_ids))
            return {"scanned": len(rows), "reaped": len(reap_ids)}
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
