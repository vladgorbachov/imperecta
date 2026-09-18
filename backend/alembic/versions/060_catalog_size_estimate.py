"""catalog_size_estimate on dim_marketplace (coverage quota, roadmap item 2).

Revision ID: 060_catalog_size_estimate
Revises: 059_price_retention_skeleton
Create Date: 2026-09-18

The >=80% coverage quota needs a denominator. Sitemap enumeration knows it
(product-like URL count per shop); this column persists the LOWER-BOUND
estimate (monotonically raised via GREATEST on rewrite — a narrower rerun
never shrinks it). Written through the META gate like the other discovery
cursor columns; /admin/parsing/coverage reads pool count vs estimate.
"""

from __future__ import annotations

from alembic import op

revision = "060_catalog_size_estimate"
down_revision = "059_price_retention_skeleton"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE dim_marketplace ADD COLUMN IF NOT EXISTS catalog_size_estimate integer"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE dim_marketplace DROP COLUMN IF EXISTS catalog_size_estimate")
