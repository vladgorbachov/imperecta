"""Price-history retention skeleton (approved policy 2026-09-18).

Revision ID: 059_price_retention_skeleton
Revises: 058_enrichment_donor_index
Create Date: 2026-09-18

Approved framework: raw fact_price rows live 12 months; older months roll
up into an eternal weekly aggregate (fact_price_weekly) and their monthly
partitions are dropped. History is never lost — only sub-week granularity
past one year. The pool itself (dim_product / fact_listing) is permanent
by policy: vanished goods flip is_active, rows are never reset.

Skeleton shipped now, ahead of need (oldest partition 202604 crosses the
12-month line in 2027-05), so the hot system is untouched later:

1. fact_price_weekly — (listing_id, week_start, currency_code) PK,
   open/close/min/max/avg + n_changes + closing price_eur.
2. maintenance.rollup_price_month(yyyymm) — aggregates ONE closed monthly
   partition into the weekly table, idempotent (ON CONFLICT DO NOTHING;
   only partitions past the cutoff are ever rolled, and nothing writes to
   them anymore).
3. maintenance.retire_price_partitions(keep_months) — for each partition
   older than the cutoff: roll up, VERIFY weekly coverage exists (or the
   raw partition was empty), only then DROP the partition. Returns what it
   retired; any verification miss raises instead of dropping.
4. pg_cron 'retire-price-history': monthly, day 1 at 04:10 UTC —
   a no-op until 2027-05 by construction.

Functions are postgres-owned SECURITY DEFINER maintenance.* per the
042/043 precedent (partition management lives DB-side, off the gate's
application write path). Plain in-transaction DDL per this repo's alembic
constraint (see 051).
"""

from __future__ import annotations

from alembic import op

revision = "059_price_retention_skeleton"
down_revision = "058_enrichment_donor_index"
branch_labels = None
depends_on = None

_SEARCH_PATH = "SET search_path = pg_catalog, public, maintenance, pg_temp"


def upgrade() -> None:
    op.execute("SET LOCAL statement_timeout = '600s'")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_price_weekly (
            listing_id uuid NOT NULL
                REFERENCES fact_listing(id) ON DELETE CASCADE,
            week_start date NOT NULL,
            currency_code varchar(3) NOT NULL,
            price_open numeric(12,2) NOT NULL,
            price_close numeric(12,2) NOT NULL,
            price_min numeric(12,2) NOT NULL,
            price_max numeric(12,2) NOT NULL,
            price_avg numeric(12,2) NOT NULL,
            price_eur_close numeric(12,2),
            n_changes integer NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (listing_id, week_start, currency_code)
        )
        """
    )
    op.execute("REVOKE ALL ON public.fact_price_weekly FROM anon, authenticated")
    op.execute("GRANT SELECT ON public.fact_price_weekly TO imperecta_app")

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION maintenance.rollup_price_month(p_yyyymm integer)
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            part_name text := format('fact_price_%s', p_yyyymm);
            rows_written integer := 0;
        BEGIN
            IF to_regclass(format('public.%I', part_name)) IS NULL THEN
                RETURN 0;
            END IF;
            EXECUTE format(
                $sql$
                INSERT INTO public.fact_price_weekly (
                    listing_id, week_start, currency_code,
                    price_open, price_close, price_min, price_max, price_avg,
                    price_eur_close, n_changes
                )
                SELECT
                    listing_id,
                    date_trunc('week', to_date(date_id::text, 'YYYYMMDD'))::date,
                    currency_code,
                    (array_agg(price ORDER BY date_id, scraped_at))[1],
                    (array_agg(price ORDER BY date_id DESC, scraped_at DESC))[1],
                    min(price), max(price), round(avg(price), 2),
                    (array_agg(price_eur ORDER BY date_id DESC, scraped_at DESC))[1],
                    count(*)
                FROM public.%I
                GROUP BY listing_id,
                         date_trunc('week', to_date(date_id::text, 'YYYYMMDD'))::date,
                         currency_code
                ON CONFLICT (listing_id, week_start, currency_code) DO NOTHING
                $sql$,
                part_name
            );
            GET DIAGNOSTICS rows_written = ROW_COUNT;
            RETURN rows_written;
        END;
        $fn$;
        """
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION maintenance.rollup_price_month(integer) FROM PUBLIC;"
    )

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION maintenance.retire_price_partitions(
            p_keep_months integer DEFAULT 12
        )
        RETURNS text[]
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            cutoff_yyyymm integer := to_char(
                date_trunc('month', now()) - make_interval(months => p_keep_months),
                'YYYYMM'
            )::integer;
            part record;
            part_yyyymm integer;
            raw_count bigint;
            weekly_count bigint;
            retired text[] := ARRAY[]::text[];
        BEGIN
            FOR part IN
                SELECT c.relname
                FROM pg_inherits i
                JOIN pg_class c ON c.oid = i.inhrelid
                JOIN pg_class p ON p.oid = i.inhparent
                WHERE p.relname = 'fact_price'
                  AND c.relname ~ '^fact_price_[0-9]{{6}}$'
                ORDER BY c.relname
            LOOP
                part_yyyymm := right(part.relname, 6)::integer;
                IF part_yyyymm >= cutoff_yyyymm THEN
                    CONTINUE;
                END IF;
                PERFORM maintenance.rollup_price_month(part_yyyymm);
                EXECUTE format('SELECT count(*) FROM public.%I', part.relname)
                    INTO raw_count;
                EXECUTE format(
                    $sql$
                    SELECT count(*) FROM public.fact_price_weekly w
                    WHERE w.week_start >= date_trunc(
                        'week', to_date(%L || '01', 'YYYYMMDD'))::date
                      AND w.week_start < (to_date(%L || '01', 'YYYYMMDD')
                          + interval '1 month')::date
                    $sql$,
                    part_yyyymm::text, part_yyyymm::text
                ) INTO weekly_count;
                IF raw_count > 0 AND weekly_count = 0 THEN
                    RAISE EXCEPTION
                        'retire_price_partitions: % has % raw rows but no weekly coverage — refusing to drop',
                        part.relname, raw_count;
                END IF;
                EXECUTE format('DROP TABLE public.%I', part.relname);
                retired := retired || part.relname;
            END LOOP;
            RETURN retired;
        END;
        $fn$;
        """
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION maintenance.retire_price_partitions(integer) FROM PUBLIC;"
    )

    op.execute(
        """
        DO $do$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'retire-price-history') THEN
                PERFORM cron.schedule(
                    'retire-price-history',
                    '10 4 1 * *',
                    'SELECT maintenance.retire_price_partitions(12)'
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
            IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'retire-price-history') THEN
                PERFORM cron.unschedule('retire-price-history');
            END IF;
        END
        $do$;
        """
    )
    op.execute(
        "DROP FUNCTION IF EXISTS maintenance.retire_price_partitions(integer)"
    )
    op.execute("DROP FUNCTION IF EXISTS maintenance.rollup_price_month(integer)")
    op.execute("DROP TABLE IF EXISTS fact_price_weekly")
