"""Fix rls_app_read on partitioned parent tables (Level 2 seam 9.3 fix).

Revision ID: 041_grant_imperecta_app_partition_parents
Revises: 040_grant_imperecta_app
Create Date: 2026-06-28

Migration 040 looped only relkind='r', skipping partitioned parents (relkind='p').
fact_price has RLS enabled on the parent but received no rls_app_read policy,
so imperecta_app would read zero rows from fact_price after seam 9.5.

This revision adds the missing policies for relkind IN ('r', 'p') with an
idempotent NOT EXISTS guard. Leaf partitions already covered by 040 are skipped.

Idle until 9.5. No DATABASE_URL switch, no DML revoke, no persist rewire.
"""

from __future__ import annotations

from alembic import op

revision = "041_grant_imperecta_app_partition_parents"
down_revision = "040_grant_imperecta_app"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            tbl record;
        BEGIN
            FOR tbl IN
                SELECT c.relname AS table_name
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind IN ('r', 'p')
                  AND c.relrowsecurity = true
                ORDER BY c.relname
            LOOP
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_policies AS p
                    WHERE p.schemaname = 'public'
                      AND p.tablename = tbl.table_name
                      AND p.policyname = 'rls_app_read'
                ) THEN
                    EXECUTE format(
                        'CREATE POLICY rls_app_read ON public.%I '
                        'FOR SELECT TO imperecta_app USING (true)',
                        tbl.table_name
                    );
                END IF;
            END LOOP;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            tbl record;
        BEGIN
            FOR tbl IN
                SELECT c.relname AS table_name
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind = 'p'
                  AND c.relrowsecurity = true
                ORDER BY c.relname
            LOOP
                IF EXISTS (
                    SELECT 1
                    FROM pg_policies AS p
                    WHERE p.schemaname = 'public'
                      AND p.tablename = tbl.table_name
                      AND p.policyname = 'rls_app_read'
                ) THEN
                    EXECUTE format(
                        'DROP POLICY IF EXISTS rls_app_read ON public.%I',
                        tbl.table_name
                    );
                END IF;
            END LOOP;
        END
        $$;
        """
    )
