"""Matching upgrade-sweep indexes (gtin + title_en late arrivals).

Revision ID: 063_match_sweep_indexes
Revises: 062_alert_in_app_channels
Create Date: 2026-09-18

Identity data can arrive AFTER a product was matched: gtin from PDP
JSON-LD scrapes, title_en from enrichment. The matching tick sweeps both
sets incrementally; these partial indexes keep each sweep an index walk.
Both shrink toward empty as sweeps drain. IF NOT EXISTS mirrors the
out-of-band CONCURRENTLY creation on the hot table; plain in-transaction
DDL only (autocommit_block is broken in this env).
"""

from __future__ import annotations

from alembic import op

revision = "063_match_sweep_indexes"
down_revision = "062_alert_in_app_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL statement_timeout = '600s'")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_product_match_gtin_sweep "
        "ON dim_product (id) "
        "WHERE sku_universal IS NOT NULL "
        "AND (match_method IS DISTINCT FROM 'gtin') AND is_active"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_product_match_title_sweep "
        "ON dim_product (id) "
        "WHERE match_method = 'unmatched' AND title_en IS NOT NULL AND is_active"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_product_match_title_sweep")
    op.execute("DROP INDEX IF EXISTS ix_product_match_gtin_sweep")
