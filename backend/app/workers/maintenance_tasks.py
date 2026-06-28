"""Maintenance tasks: materialized view refresh and fact_price partition management."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import structlog
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import select, text

from app.config import Settings
from app.database import sync_engine, sync_session_factory
from app.models.app_tables import ScrapeJob
from app.modules.core.supabase_security import harden_table_statements
from app.modules.persist.maintenance_audit import record_maintenance_audit
from app.modules.persist.retention import run_retention_pass
from app.observability.sentry_init import capture_exception_if_initialized
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)

_ALLOWED_MATERIALIZED_VIEWS: frozenset[str] = frozenset(
    {"mv_daily_price_summary", "mv_marketplace_health"},
)
_ACTIVE_SCRAPE_JOB_TYPES: tuple[str, ...] = (
    "full_pipeline_test",
    "scrape",
    "discovery",
)


def _has_active_scrape_job() -> bool:
    """True when a pipeline/scrape/discovery job is actively running.

    Uses the same scrape_jobs table signal as ParsingAdminService.get_active_pipeline_job,
    extended to running scrape/discovery children during a pipeline.
    """
    with sync_session_factory() as session:
        exists = session.execute(
            select(ScrapeJob.id)
            .where(
                ScrapeJob.status == "running",
                ScrapeJob.job_type.in_(_ACTIVE_SCRAPE_JOB_TYPES),
            )
            .limit(1),
        ).scalar_one_or_none()
        return exists is not None


def _refresh_mv(mv_name: str) -> None:
    """Refresh one materialized view non-concurrently.

    Uses a dedicated autocommit connection. Session-level work_mem applies only
    to this connection and is reset before close. The temp-file GUC is not set:
    Supabase managed Postgres forbids the owner role from setting it.
    Non-concurrent refresh avoids the temp-copy blowup that motivated the guard.
    """
    if mv_name not in _ALLOWED_MATERIALIZED_VIEWS:
        raise ValueError(f"unsupported materialized view: {mv_name}")

    settings = Settings()
    work_mem_mb = settings.mv_refresh_work_mem_mb

    raw = sync_engine.raw_connection()
    try:
        raw.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = raw.cursor()
        cur.execute(f"SET work_mem = '{work_mem_mb}MB'")
        cur.execute(f"REFRESH MATERIALIZED VIEW {mv_name}")
        cur.execute("RESET work_mem")
        cur.close()
    finally:
        raw.close()


def _refresh_one_mv(mv_name: str) -> None:
    """Refresh a single MV with timing, logging, and isolated failure handling."""
    started = time.perf_counter()
    try:
        _refresh_mv(mv_name)
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        slog.error("mv_refresh_failed", mv=mv_name, error=str(exc)[:500])
        capture_exception_if_initialized(exc)
        record_maintenance_audit(
            op="REFRESH MV",
            target=mv_name,
            status="error",
            detail=str(exc)[:2000],
            duration_ms=duration_ms,
        )
        return
    duration_ms = int(round((time.perf_counter() - started) * 1000))
    slog.info("mv_refresh_ok", mv=mv_name, duration_ms=duration_ms)
    record_maintenance_audit(
        op="REFRESH MV",
        target=mv_name,
        status="success",
        duration_ms=duration_ms,
    )


@celery_app.task(name="refresh_materialized_views")
def refresh_materialized_views() -> None:
    """Refresh materialized views without CONCURRENTLY temp-copy blowup."""
    if _has_active_scrape_job():
        slog.info("mv_refresh_skipped_active_scrape")
        return

    for mv_name in ("mv_daily_price_summary", "mv_marketplace_health"):
        _refresh_one_mv(mv_name)


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _month_start_date_id(year: int, month: int) -> int:
    return year * 10000 + month * 100 + 1


@celery_app.task(name="ensure_fact_price_partitions")
def ensure_fact_price_partitions() -> None:
    """Create fact_price partitions for the next three calendar months (rolling window)."""
    now = datetime.now(timezone.utc)
    y, m = now.year, now.month
    for offset in range(1, 4):
        cy, cm = y, m
        for _ in range(offset):
            cy, cm = _next_month(cy, cm)
        start_id = _month_start_date_id(cy, cm)
        ny, nm = _next_month(cy, cm)
        end_id = _month_start_date_id(ny, nm)
        suffix = f"{cy}{cm:02d}"
        partition_name = f"fact_price_{suffix}"
        ddl = (
            f"CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF fact_price "
            f"FOR VALUES FROM ({start_id}) TO ({end_id})"
        )
        started = time.perf_counter()
        try:
            with sync_engine.connect() as conn:
                conn.execute(text(ddl))
                qualified = f"public.{partition_name}"
                for statement in harden_table_statements(qualified):
                    conn.execute(text(statement))
                conn.commit()
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.info("Ensured partition %s (RLS + client revoke)", partition_name)
            record_maintenance_audit(
                op="CREATE PARTITION",
                target=partition_name,
                status="success",
                detail="RLS hardened via harden_table_statements",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.exception("Failed to create partition %s", partition_name)
            record_maintenance_audit(
                op="CREATE PARTITION",
                target=partition_name,
                status="error",
                detail=str(exc)[:2000],
                duration_ms=duration_ms,
            )


@celery_app.task(name="run_service_data_retention")
def run_service_data_retention() -> dict[str, int]:
    """Delete service-data rows via the gate (per-table windows, fail-open)."""
    try:
        return run_retention_pass()
    except Exception as exc:
        slog.error("retention_pass_failed", error=str(exc)[:500])
        capture_exception_if_initialized(exc)
        return {}
