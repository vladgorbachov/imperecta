"""mv_pool_stats: column unique index so CONCURRENTLY refresh works.

Revision ID: 065_mv_pool_stats_refresh_fix
Revises: 064_product_updated_at_index
Create Date: 2026-09-19

Live incident: the pg_cron 'refresh-pool-stats' job failed every 10 min
("cannot refresh materialized view concurrently") because the singleton
uniqueness index was an EXPRESSION index ((true)) — REFRESH ... CONCURRENTLY
requires a unique index on plain columns only. The UI pool counter froze at
the last successful refresh (1.46M) while the real pool reached 2.49M.

Fix: a unique index on refreshed_at (trivially unique on the one-row MV);
the expression index is dropped. Already applied out-of-band + a manual
refresh; this is the idempotent mirror.
"""

from __future__ import annotations

from alembic import op

revision = "065_mv_pool_stats_refresh_fix"
down_revision = "064_product_updated_at_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_pool_stats_refreshed "
        "ON mv_pool_stats (refreshed_at)"
    )
    op.execute("DROP INDEX IF EXISTS idx_mv_pool_stats_singleton")


def downgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_pool_stats_singleton "
        "ON mv_pool_stats ((true))"
    )
    op.execute("DROP INDEX IF EXISTS idx_mv_pool_stats_refreshed")
