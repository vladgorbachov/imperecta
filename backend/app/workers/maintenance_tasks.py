"""Maintenance tasks: materialized view refresh and fact_price partition management."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import text

from app.database import sync_engine
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _refresh_mv_concurrently(statement: str) -> None:
    """Run REFRESH MATERIALIZED VIEW CONCURRENTLY outside an explicit transaction."""
    raw = sync_engine.raw_connection()
    try:
        raw.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = raw.cursor()
        cur.execute(statement)
        cur.close()
    finally:
        raw.close()


@celery_app.task(name="refresh_materialized_views")
def refresh_materialized_views() -> None:
    """Refresh materialized views (requires unique indexes from migration 001)."""
    try:
        _refresh_mv_concurrently("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_price_summary")
        _refresh_mv_concurrently("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_marketplace_health")
        logger.info("Materialized views refreshed")
    except Exception:
        logger.exception("MV refresh failed")


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
        try:
            with sync_engine.connect() as conn:
                conn.execute(text(ddl))
                conn.commit()
            logger.info("Ensured partition %s", partition_name)
        except Exception:
            logger.exception("Failed to create partition %s", partition_name)
