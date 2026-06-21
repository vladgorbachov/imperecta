"""Supabase security hardening — codify RLS, revoke anon/authenticated Data API access.

Revision ID: 025_supabase_security_hardening
Revises: 024_reject_data_and_not_a_product
Create Date: 2026-06-20
"""

from alembic import op

from app.modules.core.supabase_security import (
    MATERIALIZED_VIEWS,
    SCHEMA_REVOKE_STATEMENTS,
    harden_materialized_view_statements,
    harden_table_statements,
    tables_needing_deny_policy,
)

revision = "025_supabase_security_hardening"
down_revision = "024_reject_data_and_not_a_product"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Codify RLS policies on partitions/reject_data/users; revoke client GraphQL grants."""
    bind = op.get_bind()
    for table in tables_needing_deny_policy(bind):
        qualified = f"public.{table}"
        for statement in harden_table_statements(qualified):
            op.execute(statement)

    for view_name in MATERIALIZED_VIEWS:
        for statement in harden_materialized_view_statements(view_name):
            op.execute(statement)

    for statement in SCHEMA_REVOKE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    """Restore broad client grants (policies remain; re-run upgrade to re-harden)."""
    op.execute(
        "GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon, authenticated",
    )
    op.execute(
        "GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated",
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT ON TABLES TO anon, authenticated",
    )
    for view_name in MATERIALIZED_VIEWS:
        qualified = f"public.{view_name}"
        op.execute(f"GRANT SELECT ON {qualified} TO anon, authenticated")
