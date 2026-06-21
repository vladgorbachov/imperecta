"""Supabase Data API hardening — RLS deny policies and client-role revokes."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

DENY_POLICY_NAME = "rls_deny_client_roles"
CLIENT_ROLES = "anon, authenticated"

MATERIALIZED_VIEWS: tuple[str, ...] = (
    "mv_daily_price_summary",
    "mv_marketplace_health",
)

EXTRA_RLS_TABLES: tuple[str, ...] = (
    "users",
    "reject_data",
)

SCHEMA_REVOKE_STATEMENTS: tuple[str, ...] = (
    "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated",
    "REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM anon, authenticated",
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated",
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM anon, authenticated",
)


def enable_rls_sql(qualified_name: str) -> str:
    """Idempotent RLS enable for one table."""
    return f"ALTER TABLE IF EXISTS {qualified_name} ENABLE ROW LEVEL SECURITY"


def drop_deny_policy_sql(qualified_name: str) -> str:
    """Drop the standard deny-all client policy if present."""
    return f"DROP POLICY IF EXISTS {DENY_POLICY_NAME} ON {qualified_name}"


def create_deny_policy_sql(qualified_name: str) -> str:
    """Deny anon/authenticated all access; table owner bypasses RLS."""
    return (
        f"CREATE POLICY {DENY_POLICY_NAME} ON {qualified_name} "
        f"FOR ALL TO {CLIENT_ROLES} USING (false) WITH CHECK (false)"
    )


def revoke_client_roles_on_relation_sql(qualified_name: str) -> tuple[str, str]:
    """Revoke table/MV privileges from Supabase client roles."""
    return (
        f"REVOKE ALL ON {qualified_name} FROM {CLIENT_ROLES}",
        f"REVOKE SELECT ON {qualified_name} FROM {CLIENT_ROLES}",
    )


def harden_table_statements(qualified_name: str) -> tuple[str, ...]:
    """RLS + deny policy + revokes for one public table (e.g. new fact_price partition)."""
    revoke_all, revoke_select = revoke_client_roles_on_relation_sql(qualified_name)
    return (
        enable_rls_sql(qualified_name),
        drop_deny_policy_sql(qualified_name),
        create_deny_policy_sql(qualified_name),
        revoke_all,
        revoke_select,
    )


def harden_materialized_view_statements(view_name: str) -> tuple[str, ...]:
    """Revoke client roles on a materialized view."""
    qualified = view_name if "." in view_name else f"public.{view_name}"
    return revoke_client_roles_on_relation_sql(qualified)


def list_fact_price_partition_names(conn: Connection) -> list[str]:
    """Return public fact_price_* partition table names."""
    rows = conn.execute(
        text(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename LIKE 'fact_price_%'
            ORDER BY tablename
            """
        ),
    ).fetchall()
    return [str(row[0]) for row in rows]


def tables_needing_deny_policy(conn: Connection) -> list[str]:
    """Tables with RLS but no policy yet (partitions, reject_data, users)."""
    extra = list(EXTRA_RLS_TABLES)
    partitions = list_fact_price_partition_names(conn)
    return extra + partitions
