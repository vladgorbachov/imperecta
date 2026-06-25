"""fact_listing.url_hash NOT NULL — canonical single-row locator.

Revision ID: 030_fact_listing_url_hash_not_null
Revises: 029_reject_data_operation
Create Date: 2026-06-17
"""

from alembic import op

revision = "030_fact_listing_url_hash_not_null"
down_revision = "029_reject_data_operation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM fact_listing WHERE url_hash IS NULL")
    op.execute("ALTER TABLE fact_listing ALTER COLUMN url_hash SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE fact_listing ALTER COLUMN url_hash DROP NOT NULL")
