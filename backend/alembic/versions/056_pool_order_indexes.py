"""Order-matching indexes for /pool/products sorts (P12 follow-up).

Revision ID: 056_pool_order_indexes
Revises: 055_enrichment_reuse_index
Create Date: 2026-09-18

Live EXPLAIN showed the default page hash-joining all 1.45M listings and
top-N-sorting them (~10s): no index matched the ORDER BY. These match the
list orderings exactly — (sort key DIR NULLS LAST, id ASC) WHERE is_active
— so the planner walks the index and nested-loops the dimensions until
LIMIT fills: 9965ms → 43ms measured. ASC NULLS LAST is not the backward
scan of DESC NULLS LAST, hence separate price indexes per direction.

Already applied to prod CONCURRENTLY out-of-band (additive, hot fix);
IF NOT EXISTS makes this a no-op there and builds them on fresh installs.
"""

from __future__ import annotations

from alembic import op

revision = "056_pool_order_indexes"
down_revision = "055_enrichment_reuse_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL statement_timeout = '600s'")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_listing_recent_order "
        "ON fact_listing (last_checked_at DESC NULLS LAST, id ASC) WHERE is_active"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_listing_price_asc_order "
        "ON fact_listing (last_price ASC NULLS LAST, id ASC) WHERE is_active"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_listing_price_desc_order "
        "ON fact_listing (last_price DESC NULLS LAST, id ASC) WHERE is_active"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_listing_price_desc_order")
    op.execute("DROP INDEX IF EXISTS idx_listing_price_asc_order")
    op.execute("DROP INDEX IF EXISTS idx_listing_recent_order")
