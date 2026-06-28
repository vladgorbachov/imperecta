"""pg_cron fact_price partition maintenance (DDL-eviction E1, decision C).

Revision ID: 042_pgcron_fact_price_partitions
Revises: 041_grant_imperecta_app_partition_parents
Create Date: 2026-06-28

Purpose: relocate fact_price partition CREATE + RLS hardening from the Celery task
(ensure_fact_price_partitions) to a postgres-owned SECURITY DEFINER routine
scheduled via pg_cron. After seam 9.5 the app role must not run DDL.

Parameterized helper maintenance._ensure_fact_price_partition(year, month) holds
all DDL; the scheduled wrapper loops offsets +1/+2/+3 from UTC now. The helper
is directly testable on throwaway months (e.g. 2099-01) without waiting for the
rolling window.

Overlap: Celery task remains until E3; both paths are idempotent. Adds rls_app_read
on new partitions (gap the app harden never covered).

Prerequisite: pg_cron extension enabled. Migration fails at schedule if absent.

No app code changes, no DATABASE_URL switch, no DML revoke, no persist rewire.
"""

from __future__ import annotations

from alembic import op

revision = "042_pgcron_fact_price_partitions"
down_revision = "041_grant_imperecta_app_partition_parents"
branch_labels = None
depends_on = None

_SEARCH_PATH = "SET search_path = pg_catalog, public, pg_temp"


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS maintenance AUTHORIZATION postgres;")

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION maintenance._ensure_fact_price_partition(
            p_year integer,
            p_month integer
        )
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            start_id integer;
            end_id integer;
            ny integer;
            nm integer;
            pname text;
        BEGIN
            start_id := p_year * 10000 + p_month * 100 + 1;

            IF p_month = 12 THEN
                ny := p_year + 1;
                nm := 1;
            ELSE
                ny := p_year;
                nm := p_month + 1;
            END IF;

            end_id := ny * 10000 + nm * 100 + 1;
            pname := 'fact_price_' || p_year::text || lpad(p_month::text, 2, '0');

            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.fact_price '
                'FOR VALUES FROM (%s) TO (%s)',
                pname,
                start_id,
                end_id
            );

            EXECUTE format(
                'ALTER TABLE IF EXISTS public.%I ENABLE ROW LEVEL SECURITY',
                pname
            );

            EXECUTE format(
                'DROP POLICY IF EXISTS rls_deny_client_roles ON public.%I',
                pname
            );

            EXECUTE format(
                'CREATE POLICY rls_deny_client_roles ON public.%I '
                'FOR ALL TO anon, authenticated '
                'USING (false) WITH CHECK (false)',
                pname
            );

            EXECUTE format(
                'REVOKE ALL ON public.%I FROM anon, authenticated',
                pname
            );

            EXECUTE format(
                'REVOKE SELECT ON public.%I FROM anon, authenticated',
                pname
            );

            IF NOT EXISTS (
                SELECT 1
                FROM pg_policy AS p
                JOIN pg_class AS c ON c.oid = p.polrelid
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname = pname
                  AND p.polname = 'rls_app_read'
            ) THEN
                EXECUTE format(
                    'CREATE POLICY rls_app_read ON public.%I '
                    'FOR SELECT TO imperecta_app USING (true)',
                    pname
                );
            END IF;
        END;
        $fn$;
        """
    )

    op.execute(
        "REVOKE EXECUTE ON FUNCTION maintenance._ensure_fact_price_partition(integer, integer) FROM PUBLIC;"
    )

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION maintenance.ensure_fact_price_partitions()
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            offset_months integer;
            ty integer;
            tm integer;
            i integer;
        BEGIN
            FOR offset_months IN 1..3 LOOP
                ty := EXTRACT(YEAR FROM (timezone('UTC', now())))::integer;
                tm := EXTRACT(MONTH FROM (timezone('UTC', now())))::integer;

                FOR i IN 1..offset_months LOOP
                    IF tm = 12 THEN
                        ty := ty + 1;
                        tm := 1;
                    ELSE
                        tm := tm + 1;
                    END IF;
                END LOOP;

                PERFORM maintenance._ensure_fact_price_partition(ty, tm);
            END LOOP;
        END;
        $fn$;
        """
    )

    op.execute(
        "REVOKE EXECUTE ON FUNCTION maintenance.ensure_fact_price_partitions() FROM PUBLIC;"
    )

    op.execute(
        """
        DO $do$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
                RAISE EXCEPTION 'pg_cron extension not installed; enable it before migration 042';
            END IF;
            PERFORM cron.schedule(
                'ensure-fact-price-partitions',
                '0 0 * * *',
                'SELECT maintenance.ensure_fact_price_partitions()'
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
            IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'ensure-fact-price-partitions') THEN
                PERFORM cron.unschedule('ensure-fact-price-partitions');
            END IF;
        END
        $do$;
        """
    )

    op.execute("DROP FUNCTION IF EXISTS maintenance.ensure_fact_price_partitions();")

    op.execute(
        "DROP FUNCTION IF EXISTS maintenance._ensure_fact_price_partition(integer, integer);"
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_namespace AS n
                WHERE n.nspname = 'maintenance'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM pg_class AS c
                      WHERE c.relnamespace = n.oid
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM pg_proc AS p
                      WHERE p.pronamespace = n.oid
                  )
            ) THEN
                DROP SCHEMA maintenance;
            END IF;
        END
        $$;
        """
    )
