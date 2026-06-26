"""Index for movers window filter on fact_listing.last_price_changed_at.

Revision ID: 031_listing_last_price_changed_idx
Revises: 030_fact_listing_url_hash_not_null
Create Date: 2026-06-17
"""

from alembic import op

revision = "031_listing_last_price_changed_idx"
down_revision = "030_fact_listing_url_hash_not_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_listing_last_price_changed_active "
        "ON fact_listing (last_price_changed_at) "
        "WHERE is_active = TRUE AND last_price_changed_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_listing_last_price_changed_active")
