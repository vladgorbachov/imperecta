"""add universal discovery columns to dim_marketplace

Revision ID: 010_discovery_universal_columns
Revises: 009_full_v2_schema_rebuild
Create Date: 2026-05-27
"""

from alembic import op

revision = "010_discovery_universal_columns"
down_revision = "009_full_v2_schema_rebuild"
branch_labels = None
depends_on = None


def _exec(sql: str) -> None:
    op.execute(sql)


def upgrade() -> None:
    _exec(
        "ALTER TABLE dim_marketplace "
        "ADD COLUMN IF NOT EXISTS discovered_category_urls JSONB "
        "NOT NULL DEFAULT '[]'::jsonb"
    )
    _exec(
        "ALTER TABLE dim_marketplace "
        "ADD COLUMN IF NOT EXISTS last_category_recon_at TIMESTAMPTZ DEFAULT NULL"
    )
    _exec(
        "ALTER TABLE dim_marketplace "
        "ADD COLUMN IF NOT EXISTS sitemap_url VARCHAR(2048) DEFAULT NULL"
    )
    _exec(
        "ALTER TABLE dim_marketplace "
        "ADD COLUMN IF NOT EXISTS last_sitemap_harvest_at TIMESTAMPTZ DEFAULT NULL"
    )


def downgrade() -> None:
    for col in (
        "discovered_category_urls",
        "last_category_recon_at",
        "sitemap_url",
        "last_sitemap_harvest_at",
    ):
        _exec(f"ALTER TABLE dim_marketplace DROP COLUMN IF EXISTS {col}")
