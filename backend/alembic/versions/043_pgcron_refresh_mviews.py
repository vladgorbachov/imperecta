"""pg_cron materialized view refresh (DDL-eviction E2, decision C).

Revision ID: 043_pgcron_refresh_mviews
Revises: 042_pgcron_fact_price_partitions
Create Date: 2026-06-28

Purpose: relocate REFRESH MATERIALIZED VIEW from the Celery task
(refresh_materialized_views) to a postgres-owned SECURITY DEFINER routine
scheduled via pg_cron. After seam 9.5 the app role must not run DDL/maintenance
REFRESH on its connection.

Overlap: Celery task remains until E3; both paths are idempotent (plain REFRESH
recompute). Skip-if-active-scrape predicate mirrors _has_active_scrape_job.

Prerequisite: pg_cron extension enabled. Migration fails at schedule if absent.
Reuses maintenance schema from migration 042.

No app code changes, no DATABASE_URL switch, no DML revoke, no persist rewire.
"""

from __future__ import annotations

from alembic import op

revision = "043_pgcron_refresh_mviews"
down_revision = "042_pgcron_fact_price_partitions"
branch_labels = None
depends_on = None

_SEARCH_PATH = "SET search_path = pg_catalog, public, pg_temp"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION maintenance.refresh_materialized_views()
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM scrape_jobs
                WHERE status = 'running'
                  AND job_type IN (
                      'full_pipeline_test',
                      'scrape',
                      'discovery'
                  )
            ) THEN
                RAISE NOTICE 'refresh skipped: active scrape job';
                RETURN;
            END IF;

            SET LOCAL work_mem = '64MB';

            REFRESH MATERIALIZED VIEW public.mv_daily_price_summary;
            REFRESH MATERIALIZED VIEW public.mv_marketplace_health;
        END;
        $fn$;
        """
    )

    op.execute(
        "REVOKE EXECUTE ON FUNCTION maintenance.refresh_materialized_views() FROM PUBLIC;"
    )

    op.execute(
        """
        DO $do$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
                RAISE EXCEPTION 'pg_cron extension not installed; enable before migration 043';
            END IF;
            PERFORM cron.schedule(
                'refresh-materialized-views',
                '0 * * * *',
                'SELECT maintenance.refresh_materialized_views()'
            );
        END
        $do$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $do$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM cron.job WHERE jobname = 'refresh-materialized-views'
            ) THEN
                PERFORM cron.unschedule('refresh-materialized-views');
            END IF;
        END
        $do$;
        """
    )

    op.execute("DROP FUNCTION IF EXISTS maintenance.refresh_materialized_views();")
