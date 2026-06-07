"""dim_marketplace recon frontier state.

Revision ID: 017_dim_marketplace_recon_frontier_state
Revises: 016_dim_marketplace_sitemap_resume_offset
Create Date: 2026-06-07

Rationale: enable resumable BFS in _phase1_category_recon. For
marketplaces whose category recon exceeds the per-marketplace budget
(thin sitemap + large, slow site), the BFS frontier (queue, visited,
partial listing_urls) is persisted to this JSONB column on deadline
expiry; the next run resumes from the saved frontier instead of
restarting from base_url. NULL means "no BFS in progress".
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "017_dim_marketplace_recon_frontier_state"
down_revision = "016_dim_marketplace_sitemap_resume_offset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dim_marketplace",
        sa.Column(
            "recon_frontier_state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("dim_marketplace", "recon_frontier_state")
