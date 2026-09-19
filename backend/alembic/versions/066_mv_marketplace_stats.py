"""mv_marketplace_stats: per-marketplace listing count + avg EUR price.

Revision ID: 066_mv_marketplace_stats
Revises: 065_mv_pool_stats_refresh_fix
Create Date: 2026-09-19

/api/pool/marketplace-stats aggregated ALL of fact_listing (2.5M rows) per
request — LEFT JOIN + GROUP BY with no covering structure — and started
hitting statement_timeout on the shared instance (Sentry PYTHON-FASTAPI-18,
recurring since 2026-09-18). Same remedy as mv_pool_stats (051): a pg_cron
refreshed materialized view, read with a cheap join on dim_marketplace.

The unique index is on a PLAIN column (marketplace_id) so REFRESH
CONCURRENTLY works — see 065 for the expression-index trap.
"""

from __future__ import annotations

from alembic import op

revision = "066_mv_marketplace_stats"
down_revision = "065_mv_pool_stats_refresh_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_marketplace_stats AS
        SELECT
            marketplace_id,
            count(*) AS listing_count,
            avg(last_price_eur) AS avg_price_eur,
            now() AS refreshed_at
        FROM fact_listing
        WHERE is_active
        GROUP BY marketplace_id
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_marketplace_stats_marketplace "
        "ON mv_marketplace_stats (marketplace_id)"
    )
    op.execute("REVOKE ALL ON public.mv_marketplace_stats FROM anon, authenticated")
    op.execute("GRANT SELECT ON public.mv_marketplace_stats TO imperecta_app")
    # Offset from refresh-pool-stats (*/10) so the two refreshes never share
    # a minute on the write-heavy instance.
    op.execute(
        """
        DO $do$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
                RAISE EXCEPTION 'pg_cron extension not installed; enable before migration 066';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'refresh-marketplace-stats') THEN
                PERFORM cron.schedule(
                    'refresh-marketplace-stats',
                    '5-59/10 * * * *',
                    'REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_marketplace_stats'
                );
            END IF;
        END
        $do$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $do$
        BEGIN
            IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'refresh-marketplace-stats') THEN
                PERFORM cron.unschedule('refresh-marketplace-stats');
            END IF;
        END
        $do$;
        """
    )
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_marketplace_stats")
