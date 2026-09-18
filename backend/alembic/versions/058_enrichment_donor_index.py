"""Partial donor index for the enrichment reuse pass.

Revision ID: 058_enrichment_donor_index
Revises: 057_last_price_change_denorm
Create Date: 2026-09-18

The reuse pass now drives from enriched DONORS (two bounded phases — the
single self-join let the planner drive from the 1.45M untyped side and hit
the 300s statement timeout live). This partial index makes the donor slice
an index-only walk regardless of pool size; it is tiny (only enriched rows
enter it). Plain in-transaction build per this repo's alembic constraint.
"""

from __future__ import annotations

from alembic import op

revision = "058_enrichment_donor_index"
down_revision = "057_last_price_change_denorm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL statement_timeout = '600s'")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_dim_product_enriched_donor "
        "ON dim_product (name_normalized) "
        "WHERE product_type_en IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_dim_product_enriched_donor")
