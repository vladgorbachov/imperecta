"""dim_marketplace sitemap resume offset.

Revision ID: 016_dim_marketplace_sitemap_resume_offset
Revises: 015_fact_price_default_partition
Create Date: 2026-06-07

Rationale: enable resumable sitemap discovery. Large sitemaps (klick.ee ~49k
URLs) cannot be persisted within DISCOVERY_PER_MARKETPLACE_BUDGET_SECONDS in a
single discover() invocation. The new column lets a partial-budget run record
the absolute offset into the sitemap URL list at which the next run should
resume, so progress survives both the per-marketplace budget and any external
cancellation. Default 0 means "start from the beginning".
"""

import sqlalchemy as sa
from alembic import op

revision = "016_dim_marketplace_sitemap_resume_offset"
down_revision = "015_fact_price_default_partition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dim_marketplace",
        sa.Column(
            "sitemap_resume_offset",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("dim_marketplace", "sitemap_resume_offset")
