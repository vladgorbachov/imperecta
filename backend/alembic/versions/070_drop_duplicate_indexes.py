"""Drop 9 duplicate / never-used indexes on the pool tables.

Revision ID: 070_drop_duplicate_indexes
Revises: 069_gate_exec_write_rows
Create Date: 2026-09-19

pg_stat_user_indexes in prod (2026-09-19): each of these had an exact
twin that carries the reads, or no reads at all — yet every insert into
the 3.5M-row pool tables maintained them (fact_listing carried 24 indexes,
3.1 GB, against 512 MB shared_buffers). Dropped CONCURRENTLY out-of-band
in prod; this is the replay mirror and the ORM no longer declares them.

  fact_listing: ix_fact_listing_product_id (0 scans; twin idx_listing_product),
    ix_fact_listing_marketplace_id (twin idx_listing_marketplace),
    ix_fact_listing_seller_id (twin idx_listing_seller),
    ix_fact_listing_is_active (twin idx_listing_active),
    idx_listing_never_checked (0 scans; superseded by 068).
  dim_product: idx_product_name (GIN on name_normalized, 377 MB, 0 scans;
    searches use idx_dim_product_name_trgm on name), ix_dim_product_brand_id
    (twin idx_product_brand), ix_dim_product_category_id (twin
    idx_product_category), idx_product_attributes (GIN, 0 scans).
"""

from __future__ import annotations

from alembic import op

revision = "070_drop_duplicate_indexes"
down_revision = "069_gate_exec_write_rows"
branch_labels = None
depends_on = None

_INDEXES = (
    "ix_fact_listing_product_id",
    "ix_fact_listing_marketplace_id",
    "ix_fact_listing_seller_id",
    "ix_fact_listing_is_active",
    "idx_listing_never_checked",
    "idx_product_name",
    "ix_dim_product_brand_id",
    "ix_dim_product_category_id",
    "idx_product_attributes",
)


def upgrade() -> None:
    for name in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")


def downgrade() -> None:
    # Only the two ORM-declared ones are recreated; the ix_* twins never
    # came from a migration.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_name ON dim_product "
        "USING gin (name_normalized gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_attributes ON dim_product USING gin (attributes)"
    )
