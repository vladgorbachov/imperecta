"""fact_listing.sitemap_lastmod — the shop's own change signal.

Revision ID: 067_listing_sitemap_lastmod
Revises: 066_mv_marketplace_stats
Create Date: 2026-09-19

Harvest optimisation #6: product sitemaps carry <lastmod>; a weekly
re-scan of the sitemap files (one paid no-JS request per file) tells which
listings the shop itself says changed since our last check, so paid PDP
fetches go to those first instead of to the stalest by age. Nullable
column, metadata-only ALTER (instant on the 3M-row table).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "067_listing_sitemap_lastmod"
down_revision = "066_mv_marketplace_stats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE fact_listing ADD COLUMN IF NOT EXISTS sitemap_lastmod "
        "TIMESTAMP WITH TIME ZONE NULL"
    )


def downgrade() -> None:
    op.drop_column("fact_listing", "sitemap_lastmod")
