"""Grant least-privilege access to imperecta_app (Level 2 seam 9.3).

Revision ID: 040_grant_imperecta_app
Revises: 039_gate_security_definer_functions
Create Date: 2026-06-28

Purpose: idle until seam 9.5 (DATABASE_URL switch). imperecta_app (NOBYPASSRLS)
receives EXECUTE on the two gate entry points, broad SELECT on public tables,
rls_app_read on every RLS-enabled table, the reject_data direct-INSERT carve-out
(write_reject_data / write_reject_data_isolated — must stay excluded from 9.6
DML revoke), and USAGE on sequences the app calls nextval() on directly.

No INSERT/UPDATE/DELETE on any table except reject_data INSERT. No EXECUTE on
gate internal helpers. No change to anon/authenticated policies or RLS flags.
"""

from __future__ import annotations

from alembic import op

revision = "040_grant_imperecta_app"
down_revision = "039_gate_security_definer_functions"
branch_labels = None
depends_on = None

# Sequences referenced by direct nextval() or identity default on carve-out INSERT.
_APP_SEQUENCE_NAMES: tuple[str, ...] = (
    "ai_chat_messages_id_seq",
    "reject_data_id_seq",
)

_EXEC_WRITE_SIGNATURE = (
    "gate.exec_write(text, text, gate.field_entry[], gate.field_entry[], text)"
)
_EXEC_WRITE_BATCH_SIGNATURE = (
    "gate.exec_write_batch(text, text, gate.field_entry[], gate.row_payload[], text)"
)

def upgrade() -> None:
    op.execute("GRANT USAGE ON SCHEMA gate TO imperecta_app;")

    op.execute("GRANT USAGE ON SCHEMA public TO imperecta_app;")

    op.execute(f"GRANT EXECUTE ON FUNCTION {_EXEC_WRITE_SIGNATURE} TO imperecta_app;")

    op.execute(f"GRANT EXECUTE ON FUNCTION {_EXEC_WRITE_BATCH_SIGNATURE} TO imperecta_app;")

    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO imperecta_app;")

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
                  AND c.relkind = 'r'
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

    op.execute("GRANT INSERT ON reject_data TO imperecta_app;")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_policies AS p
                WHERE p.schemaname = 'public'
                  AND p.tablename = 'reject_data'
                  AND p.policyname = 'rls_app_reject_insert'
            ) THEN
                CREATE POLICY rls_app_reject_insert ON reject_data
                    FOR INSERT TO imperecta_app
                    WITH CHECK (true);
            END IF;
        END
        $$;
        """
    )

    for sequence_name in _APP_SEQUENCE_NAMES:
        op.execute(f"GRANT USAGE ON SEQUENCE public.{sequence_name} TO imperecta_app;")

    op.execute(
        """
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
        GRANT SELECT ON TABLES TO imperecta_app;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
        REVOKE SELECT ON TABLES FROM imperecta_app;
        """
    )

    for sequence_name in reversed(_APP_SEQUENCE_NAMES):
        op.execute(f"REVOKE USAGE ON SEQUENCE public.{sequence_name} FROM imperecta_app;")

    op.execute("DROP POLICY IF EXISTS rls_app_reject_insert ON reject_data;")

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
                  AND c.relkind = 'r'
                  AND c.relrowsecurity = true
                ORDER BY c.relname
            LOOP
                EXECUTE format(
                    'DROP POLICY IF EXISTS rls_app_read ON public.%I',
                    tbl.table_name
                );
            END LOOP;
        END
        $$;
        """
    )

    op.execute("REVOKE INSERT ON reject_data FROM imperecta_app;")

    op.execute("REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM imperecta_app;")

    op.execute(f"REVOKE EXECUTE ON FUNCTION {_EXEC_WRITE_BATCH_SIGNATURE} FROM imperecta_app;")

    op.execute(f"REVOKE EXECUTE ON FUNCTION {_EXEC_WRITE_SIGNATURE} FROM imperecta_app;")

    op.execute("REVOKE USAGE ON SCHEMA public FROM imperecta_app;")

    op.execute("REVOKE USAGE ON SCHEMA gate FROM imperecta_app;")
