"""pg_cron fact_price partition maintenance (DDL-eviction E1, decision C).

Revision ID: 042_pgcron_fact_price_partitions
Revises: 041_grant_imperecta_app_partition_parents
Create Date: 2026-06-28

Purpose: relocate fact_price partition CREATE + RLS hardening from the Celery task
(ensure_fact_price_partitions) to a postgres-owned SECURITY DEFINER routine
scheduled via pg_cron. After seam 9.5 the app role must not run DDL.

Overlap: Celery task remains until E3; both paths are idempotent (IF NOT EXISTS /
DROP+CREATE deny policy). This routine additionally creates rls_app_read on new
partitions — closing the gap the app harden_table_statements never covered.

Prerequisite: pg_cron extension enabled (Supabase: Database → Extensions →
pg_cron). Migration fails at schedule time if pg_cron is absent.

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
        CREATE OR REPLACE FUNCTION maintenance.ensure_fact_price_partitions()
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            offset_months integer;
            cy integer;
            cm integer;
            ny integer;
            nm integer;
            i integer;
            start_id integer;
            end_id integer;
            pname text;
        BEGIN
            FOR offset_months IN 1..3 LOOP
                cy := EXTRACT(YEAR FROM (timezone('UTC', now())))::integer;
                cm := EXTRACT(MONTH FROM (timezone('UTC', now())))::integer;

                FOR i IN 1..offset_months LOOP
                    IF cm = 12 THEN
                        cy := cy + 1;
                        cm := 1;
                    ELSE
                        cm := cm + 1;
                    END IF;
                END LOOP;

                IF cm = 12 THEN
                    ny := cy + 1;
                    nm := 1;
                ELSE
                    ny := cy;
                    nm := cm + 1;
                END IF;

                start_id := cy * 10000 + cm * 100 + 1;
                end_id := ny * 10000 + nm * 100 + 1;
                pname := 'fact_price_' || cy::text || lpad(cm::text, 2, '0');

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
