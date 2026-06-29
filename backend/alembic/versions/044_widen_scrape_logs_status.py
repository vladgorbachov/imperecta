"""Widen scrape_logs.status to VARCHAR(50) (DDL-eviction E3a).

Revision ID: 044_widen_scrape_logs_status
Revises: 043_pgcron_refresh_mviews
Create Date: 2026-06-29

Purpose: fix real schema drift — production scrape_logs.status remained
VARCHAR(20) while the ORM model uses String(50) and canonical terminal status
``missing_critical_data`` is 21 characters. A runtime ALTER repair in
scraper/service.py masked the drift; that repair is removed in E3a.

``mv_marketplace_health`` depends on ``scrape_logs.status``; Postgres blocks
ALTER TYPE until the MV is dropped and recreated (metadata-only widen on the
column; MV is rebuilt + refreshed).

No app DATABASE_URL switch, no DML revoke, no persist rewire.
"""

from __future__ import annotations

from alembic import op

from app.modules.core.supabase_security import harden_materialized_view_statements

revision = "044_widen_scrape_logs_status"
down_revision = "043_pgcron_refresh_mviews"
branch_labels = None
depends_on = None

_MV_MARKETPLACE_HEALTH_SQL = """
CREATE MATERIALIZED VIEW public.mv_marketplace_health AS
SELECT
    dm.id AS marketplace_id,
    dm.marketplace_code,
    dm.name,
    dm.country_code,
    COUNT(DISTINCT fl.id) AS active_listings,
    COUNT(DISTINCT sl.id) FILTER (WHERE sl.created_at > now() - interval '24 hours') AS scrapes_24h,
    COUNT(DISTINCT sl.id) FILTER (WHERE sl.status = 'success' AND sl.created_at > now() - interval '24 hours') AS success_24h,
    COUNT(DISTINCT sl.id) FILTER (WHERE sl.status = 'error' AND sl.created_at > now() - interval '24 hours') AS errors_24h,
    CASE
        WHEN COUNT(DISTINCT sl.id) FILTER (WHERE sl.created_at > now() - interval '24 hours') = 0 THEN 0::NUMERIC
        ELSE (
            COUNT(DISTINCT sl.id) FILTER (WHERE sl.status = 'success' AND sl.created_at > now() - interval '24 hours')::NUMERIC
            / NULLIF(COUNT(DISTINCT sl.id) FILTER (WHERE sl.created_at > now() - interval '24 hours'), 0)
        )
    END AS success_rate_24h,
    AVG(sl.duration_ms) FILTER (WHERE sl.created_at > now() - interval '24 hours') AS avg_duration_ms_24h
FROM dim_marketplace dm
LEFT JOIN fact_listing fl ON dm.id = fl.marketplace_id AND fl.is_active = true
LEFT JOIN scrape_logs sl ON dm.id = sl.marketplace_id
GROUP BY dm.id, dm.marketplace_code, dm.name, dm.country_code
WITH NO DATA
"""


def _recreate_mv_marketplace_health() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_marketplace_health "
        "ON public.mv_marketplace_health (marketplace_id)"
    )
    for statement in harden_materialized_view_statements("mv_marketplace_health"):
        op.execute(statement)
    op.execute("REFRESH MATERIALIZED VIEW public.mv_marketplace_health")


def upgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS public.mv_marketplace_health")
    op.execute("ALTER TABLE scrape_logs ALTER COLUMN status TYPE VARCHAR(50)")
    op.execute(_MV_MARKETPLACE_HEALTH_SQL)
    _recreate_mv_marketplace_health()


def downgrade() -> None:
    # Formal reverse; fails if any stored status exceeds 20 characters.
    op.execute("DROP MATERIALIZED VIEW IF EXISTS public.mv_marketplace_health")
    op.execute("ALTER TABLE scrape_logs ALTER COLUMN status TYPE VARCHAR(20)")
    op.execute(_MV_MARKETPLACE_HEALTH_SQL)
    _recreate_mv_marketplace_health()
