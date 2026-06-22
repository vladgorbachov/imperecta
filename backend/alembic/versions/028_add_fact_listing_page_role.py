"""Add fact_listing.page_role for product-ness gate diagnostics.

Revision ID: 028_add_fact_listing_page_role
Revises: 027_remove_in_stock_and_fact_stock
Create Date: 2026-06-17
"""

from alembic import op

revision = "028_add_fact_listing_page_role"
down_revision = "027_remove_in_stock_and_fact_stock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE fact_listing ADD COLUMN IF NOT EXISTS page_role varchar(16)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE fact_listing DROP COLUMN IF EXISTS page_role")
