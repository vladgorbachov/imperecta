"""Denormalized last_price_change_pct + movement sort indexes.

Revision ID: 057_last_price_change_denorm
Revises: 056_pool_order_indexes
Create Date: 2026-09-18

Algorithm audit: every pool list/detail/export query windowed the WHOLE
fact_price table to recover the latest price_change_pct per listing —
O(price history) per request, unbounded growth as harvest ramps. The pct
is now mirrored onto fact_listing at the moment the fact_price row is
written (listing_denorm_success door), read O(1), and the three movement
sorts get order-matching partial indexes (abs() is IMMUTABLE, so the
volatile expression is indexable — unlike timestamptz arithmetic, see 052).

Backfill copies the pct from each listing's latest fact_price row; plain
in-transaction builds per this repo's alembic constraint (see 051).
"""

from __future__ import annotations

from alembic import op

revision = "057_last_price_change_denorm"
down_revision = "056_pool_order_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL statement_timeout = '600s'")
    op.execute(
        "ALTER TABLE fact_listing ADD COLUMN IF NOT EXISTS last_price_change_pct numeric(8,4)"
    )
    op.execute(
        """
        UPDATE fact_listing fl
        SET last_price_change_pct = latest.price_change_pct
        FROM (
            SELECT DISTINCT ON (listing_id) listing_id, price_change_pct
            FROM fact_price
            ORDER BY listing_id, date_id DESC, scraped_at DESC
        ) latest
        WHERE latest.listing_id = fl.id
          AND latest.price_change_pct IS NOT NULL
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_listing_pct_desc_order "
        "ON fact_listing (last_price_change_pct DESC NULLS LAST, id ASC) "
        "WHERE is_active"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_listing_pct_asc_order "
        "ON fact_listing (last_price_change_pct ASC NULLS LAST, id ASC) "
        "WHERE is_active"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_listing_pct_abs_order "
        "ON fact_listing (abs(last_price_change_pct) DESC NULLS LAST, id ASC) "
        "WHERE is_active"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_listing_pct_abs_order")
    op.execute("DROP INDEX IF EXISTS idx_listing_pct_asc_order")
    op.execute("DROP INDEX IF EXISTS idx_listing_pct_desc_order")
    op.execute("ALTER TABLE fact_listing DROP COLUMN IF EXISTS last_price_change_pct")
