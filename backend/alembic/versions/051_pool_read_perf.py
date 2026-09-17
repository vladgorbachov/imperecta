"""Read-path performance for the 1.4M-row pool (pool/stats, kpi-history, volatility).

Revision ID: 051_pool_read_perf
Revises: 050_service_alerts_update
Create Date: 2026-09-18

After sitemap-full enumeration fact_listing grew ~76k -> 1.4M rows (~1.1 GB);
each dashboard load fired several sequential scans of it (plus one of
dim_product) and read endpoints started hitting the 2-minute statement_timeout
(Sentry PYTHON-FASTAPI-X/11/W). Read-path fixes only — no write-path changes:

1. mv_pool_stats — single-row pre-aggregated counts for /api/pool/stats
   (was 5 queries, 2 of them full fact_listing scans + 1 full dim_product
   scan, per request). Refreshed by pg_cron every 10 minutes. Unlike 043,
   the REFRESH is scheduled as a bare statement, not wrapped in a
   maintenance.* plpgsql function: REFRESH ... CONCURRENTLY refuses to run
   inside a transaction block (and thus inside any function), and
   CONCURRENTLY is required so the refresh never blocks /api/pool/stats
   reads. The job runs as postgres (the migration role scheduling it),
   matching the postgres-owned-maintenance rule from 042/043; the unique
   singleton index exists for REFRESH ... CONCURRENTLY.
2. Partial index on fact_listing(created_at) for the visible-product pool
   grain — /api/markets/kpi-history pool-entry queries stop seq-scanning.
3. Partial index on fact_listing(last_price) WHERE last_price IS NOT NULL —
   priced-listing counts and price sorts touch only harvested rows.
4. fact_price (listing_id, date_id, scraped_at DESC) replaces the redundant
   (listing_id, date_id) prefix index — serves the latest-scrape-per-day
   dedupe (volatility, kpi-history, price history) without a sort as
   harvest volume grows; new partitions inherit it from the parent.

Locking (agreed with the scraper session — enumeration writes fact_listing
continuously): index builds are plain in-transaction CREATE INDEX. The
CONCURRENTLY + autocommit_block variant is impossible in this project's
alembic env: migrations run through an async engine bridge where alembic
does not own a committable transaction, and autocommit_block() dies with
AssertionError (observed on deploys e592d972/7fa6e57e/80094a3e,
2026-09-18). A plain build takes a SHARE lock for the build duration
(seconds to low tens of seconds at 1.4M rows); worker writes queue behind
it (their statement_timeout is 300s) instead of failing. fact_price is a
partitioned parent where CONCURRENTLY is unsupported anyway; the new index
is created before the superseded one is dropped. The migration session
raises its own statement_timeout because env.py's default (60s) is too
tight for the fact_listing builds.

Client roles (anon/authenticated) are revoked on mv_pool_stats; imperecta_app
gets SELECT. mv_pool_stats is intentionally NOT added to
supabase_security.MATERIALIZED_VIEWS: migration 025 iterates that tuple and
runs before this view exists on fresh installs.
"""

from __future__ import annotations

from alembic import op

revision = "051_pool_read_perf"
down_revision = "050_service_alerts_update"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL statement_timeout = '600s'")
    # -- kpi-history pool entries: count(created_at < start) + group by day.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_listing_pool_entry_created "
        "ON fact_listing (created_at) "
        "WHERE is_active = TRUE AND page_role = 'product'"
    )
    # -- priced-listing counts / price sorts (tiny while harvest ramps up).
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_listing_active_priced "
        "ON fact_listing (last_price) "
        "WHERE is_active = TRUE AND last_price IS NOT NULL"
    )

    # -- latest-scrape-per-day dedupe order; supersedes the 2-column prefix.
    #    Partitioned parent: CONCURRENTLY unsupported, plain build is safe at
    #    the current ~1k-row volume. New index first, then drop the old one.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fact_price_listing_date_scraped "
        "ON fact_price (listing_id, date_id, scraped_at DESC)"
    )
    op.execute("DROP INDEX IF EXISTS idx_fact_price_listing_date")

    # -- pre-aggregated pool stats (single row).
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_pool_stats AS
        SELECT
            (SELECT count(*) FROM dim_product) AS total_products,
            (SELECT count(*) FROM dim_marketplace WHERE is_active = TRUE)
                AS marketplaces_count,
            (SELECT max(last_discovery_at) FROM dim_marketplace) AS last_updated,
            count(*) FILTER (WHERE is_active) AS total_listings,
            count(*) FILTER (WHERE is_active AND last_price IS NOT NULL)
                AS listings_with_price,
            now() AS refreshed_at
        FROM fact_listing
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_pool_stats_singleton "
        "ON mv_pool_stats ((TRUE))"
    )
    op.execute("REVOKE ALL ON public.mv_pool_stats FROM anon, authenticated")
    op.execute("REVOKE SELECT ON public.mv_pool_stats FROM anon, authenticated")
    op.execute("GRANT SELECT ON public.mv_pool_stats TO imperecta_app")

    op.execute(
        """
        DO $do$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
                RAISE EXCEPTION 'pg_cron extension not installed; enable before migration 051';
            END IF;
            PERFORM cron.schedule(
                'refresh-pool-stats',
                '*/10 * * * *',
                'REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_pool_stats'
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
            IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'refresh-pool-stats') THEN
                PERFORM cron.unschedule('refresh-pool-stats');
            END IF;
        END
        $do$;
        """
    )
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_pool_stats")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_fact_price_listing_date "
        "ON fact_price (listing_id, date_id)"
    )
    op.execute("DROP INDEX IF EXISTS idx_fact_price_listing_date_scraped")
    op.execute("DROP INDEX IF EXISTS idx_listing_active_priced")
    op.execute("DROP INDEX IF EXISTS idx_listing_pool_entry_created")
