"""idx_listing_shop_checked_active — per-shop stalest-first frontier.

Revision ID: 068_listing_shop_checked_index
Revises: 067_listing_sitemap_lastmod
Create Date: 2026-09-19

The cost-aware PDP frontier takes the N stalest due listings PER SHOP
(LATERAL per marketplace) so one giant backlog cannot fill every shard.
Without this index that walk sorted the whole 3.5M-row table per tick
(9.1s, 150k buffers); with it each shop is an ordered index range scan
that stops after N rows (96ms, 860 buffers — measured 2026-09-19).
Built CONCURRENTLY out-of-band in prod; this is the replay mirror.
"""

from __future__ import annotations

from alembic import op

revision = "068_listing_shop_checked_index"
down_revision = "067_listing_sitemap_lastmod"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_listing_shop_checked_active "
        "ON fact_listing (marketplace_id, last_checked_at ASC NULLS FIRST) "
        "WHERE is_active"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_listing_shop_checked_active")
