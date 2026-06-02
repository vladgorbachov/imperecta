"""Add scrape_tier to dim_marketplace for multi-tier scraping strategy.

Revision ID: 014_marketplace_scrape_tier
Revises: 013_search_trend_source_generic
Create Date: 2026-05-31
"""

from alembic import op

revision = "014_marketplace_scrape_tier"
down_revision = "013_search_trend_source_generic"
branch_labels = None
depends_on = None


def _exec(sql: str) -> None:
    op.execute(sql)


def upgrade() -> None:
    # Add scrape_tier column.
    # Tier 1 — server-rendered shops (Decodo + httpx + Playwright fallback).
    # Tier 2 — modern SPA shops (adds network interception + basic stealth).
    # Tier 3 — hostile marketplaces (adds full stealth + residential sticky + LLM fallback).
    # Default 1 keeps backward compatibility: all existing marketplaces continue in current mode.
    _exec(
        "ALTER TABLE dim_marketplace "
        "ADD COLUMN IF NOT EXISTS scrape_tier INTEGER NOT NULL DEFAULT 1"
    )
    _exec(
        "ALTER TABLE dim_marketplace "
        "DROP CONSTRAINT IF EXISTS ck_dim_marketplace_scrape_tier"
    )
    _exec(
        "ALTER TABLE dim_marketplace "
        "ADD CONSTRAINT ck_dim_marketplace_scrape_tier "
        "CHECK (scrape_tier IN (1, 2, 3))"
    )
    _exec(
        "CREATE INDEX IF NOT EXISTS idx_marketplace_scrape_tier "
        "ON dim_marketplace (scrape_tier)"
    )


def downgrade() -> None:
    _exec("DROP INDEX IF EXISTS idx_marketplace_scrape_tier")
    _exec(
        "ALTER TABLE dim_marketplace "
        "DROP CONSTRAINT IF EXISTS ck_dim_marketplace_scrape_tier"
    )
    _exec("ALTER TABLE dim_marketplace DROP COLUMN IF EXISTS scrape_tier")
