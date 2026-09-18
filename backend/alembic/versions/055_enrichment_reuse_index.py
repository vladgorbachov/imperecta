"""Index for the enrichment duplicate-reuse pass (P13, credit saver).

Revision ID: 055_enrichment_reuse_index
Revises: 054_product_type_en_layer
Create Date: 2026-09-18

The reuse pass self-joins dim_product on name_normalized to copy existing
type/EN enrichment onto identical products before any LLM call. At 1.45M
rows that join needs a btree on name_normalized (also serves the
DISTINCT ON dedupe in the LLM batch picker). Plain in-transaction build —
see 051 for why CONCURRENTLY is unavailable in this alembic env.
"""

from __future__ import annotations

from alembic import op

revision = "055_enrichment_reuse_index"
down_revision = "054_product_type_en_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL statement_timeout = '600s'")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_dim_product_name_normalized "
        "ON dim_product (name_normalized)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_dim_product_name_normalized")
