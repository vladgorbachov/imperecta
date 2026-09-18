"""Cross-shop matching columns on dim_product (roadmap item 3, slice M1).

Revision ID: 061_product_match_columns
Revises: 060_catalog_size_estimate
Create Date: 2026-09-18

match_group_id: deterministic uuid5 over (brand token, strongest model
code) — one group = one real-world product across shops (P6 backbone).
match_method: 'brand_model' | 'unmatched' (reserved: 'gtin','title_sim');
NULL = not yet processed by the matching tick. match_confidence: 0.90 for
known-brand signatures, 0.75 heuristic.

Indexes may be pre-created CONCURRENTLY out-of-band (hot 1.75M-row table);
IF NOT EXISTS makes this migration the idempotent mirror. Plain
in-transaction DDL only — autocommit_block is broken in this env.
"""

from __future__ import annotations

from alembic import op

revision = "061_product_match_columns"
down_revision = "060_catalog_size_estimate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL statement_timeout = '600s'")
    op.execute(
        "ALTER TABLE dim_product ADD COLUMN IF NOT EXISTS match_group_id uuid"
    )
    op.execute(
        "ALTER TABLE dim_product ADD COLUMN IF NOT EXISTS match_method varchar(16)"
    )
    op.execute(
        "ALTER TABLE dim_product ADD COLUMN IF NOT EXISTS match_confidence numeric(3,2)"
    )
    # Group lookup (P6 read path: all products of one cross-shop group).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_product_match_group "
        "ON dim_product (match_group_id) "
        "WHERE match_group_id IS NOT NULL"
    )
    # Pending-work driver for the matching tick; shrinks to nothing as the
    # backlog drains. Predicate matches the engine WHERE verbatim (bare
    # boolean column — .is_(True) renders IS TRUE and breaks the match).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_product_match_pending "
        "ON dim_product (id) "
        "WHERE match_method IS NULL AND is_active"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_product_match_pending")
    op.execute("DROP INDEX IF EXISTS ix_product_match_group")
    op.execute("ALTER TABLE dim_product DROP COLUMN IF EXISTS match_confidence")
    op.execute("ALTER TABLE dim_product DROP COLUMN IF EXISTS match_method")
    op.execute("ALTER TABLE dim_product DROP COLUMN IF EXISTS match_group_id")
