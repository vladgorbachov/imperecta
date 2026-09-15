"""Alert trigger tasks: periodic evaluation of user alert rules.

DB access follows the Pattern-A worker bridge (see `app.workers.reaper_tasks`
and `app.modules.scraper.tasks`): a Celery task must NOT touch the module-level
`app.database` async engine — its asyncpg pool is bound to whatever event loop
first created the connections, while `asyncio.run()` spins a fresh loop per
invocation ("got Future attached to a different loop" / "Event loop is
closed"). Instead, build a fresh engine inside the task's own loop and dispose
it before the loop closes.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.modules.alerts.engine import evaluate_alert_rules
from app.observability.sentry_init import capture_exception_if_initialized
from app.workers.celery_app import celery_app

slog = structlog.get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task safely (Pattern-A bridge)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="alerts-async-bridge") as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


def _make_session_factory() -> tuple:
    """Fresh async engine + sessionmaker per task invocation (Pattern-A).

    The caller MUST `await engine.dispose()` in a `finally` block so no asyncpg
    connection outlives the event loop that created it.
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


async def _run_evaluation() -> dict[str, int]:
    engine, factory = _make_session_factory()
    try:
        async with factory() as db:
            return await evaluate_alert_rules(db)
    finally:
        await engine.dispose()


@celery_app.task(name="evaluate_price_alerts")
def evaluate_price_alerts() -> dict[str, int]:
    """Run the alert trigger engine once (reads ORM, writes via ALERT door)."""
    try:
        summary = _run_async(_run_evaluation())
        if summary.get("fired"):
            slog.info("alert_rules_fired", **summary)
        return summary
    except Exception as exc:
        slog.error("alert_evaluation_failed", error=str(exc)[:500])
        capture_exception_if_initialized(exc)
        return {}
