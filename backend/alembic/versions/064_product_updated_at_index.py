"""dim_product.updated_at partial index (data-ops index delta refresh).

Revision ID: 064_product_updated_at_index
Revises: 063_match_sweep_indexes
Create Date: 2026-09-19

The data-ops in-memory name index pulls `updated_at > watermark` every
60s; without this index that is a 2.4M-row sort each minute that held the
service's whole connection pool (observed acquire timeouts). Pre-created
CONCURRENTLY out-of-band; IF NOT EXISTS mirror, plain in-transaction DDL.
"""

from __future__ import annotations

from alembic import op

revision = "064_product_updated_at_index"
down_revision = "063_match_sweep_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL statement_timeout = '600s'")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_product_updated_active "
        "ON dim_product (updated_at) WHERE is_active"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_product_updated_active")
