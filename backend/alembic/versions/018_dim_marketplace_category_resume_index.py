"""dim_marketplace category resume index.

Revision ID: 018_dim_marketplace_category_resume_index
Revises: 017_dim_marketplace_recon_frontier_state
Create Date: 2026-06-07

Rationale: enable resumable category harvest. _phase2_product_harvest
processes a window of categories per run; this column records the
absolute index into the category list at which the next run should
resume. Default 0 means "start from the beginning". The cursor resets
to 0 on full completion / convergence and when phase1 rebuilds the
category list.
"""

import sqlalchemy as sa
from alembic import op

revision = "018_dim_marketplace_category_resume_index"
down_revision = "017_dim_marketplace_recon_frontier_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dim_marketplace",
        sa.Column(
            "category_resume_index",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("dim_marketplace", "category_resume_index")
