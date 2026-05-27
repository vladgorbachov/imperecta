"""add is_active to fact_listing and no_change status to scrape_logs

Revision ID: 011_dedup_and_listing_lifecycle
Revises: 010_discovery_universal_columns
Create Date: 2026-05-27
"""

from alembic import op

revision = "011_dedup_and_listing_lifecycle"
down_revision = "010_discovery_universal_columns"
branch_labels = None
depends_on = None


def _exec(sql: str) -> None:
    op.execute(sql)


def upgrade() -> None:
    _exec(
        "ALTER TABLE fact_listing "
        "ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"
    )
    _exec(
        "ALTER TABLE fact_listing "
        "ADD COLUMN IF NOT EXISTS last_price_changed_at TIMESTAMPTZ DEFAULT NULL"
    )
    _exec(
        "CREATE INDEX IF NOT EXISTS ix_fact_listing_is_active "
        "ON fact_listing (is_active) WHERE is_active = TRUE"
    )
    _exec(
        "ALTER TABLE scrape_logs "
        "DROP CONSTRAINT IF EXISTS ck_scrape_logs_status"
    )
    _exec(
        "ALTER TABLE scrape_logs "
        "DROP CONSTRAINT IF EXISTS scrape_logs_status_check"
    )
    _exec(
        "ALTER TABLE scrape_logs ADD CONSTRAINT ck_scrape_logs_status "
        "CHECK (status IN ("
        "'success', 'no_change', 'error', 'timeout', 'blocked', 'captcha', "
        "'not_found', 'price_not_found', 'parse_error', 'missing_critical_data', "
        "'technical_error', 'fetch_failed', 'parse_failed', 'quota_exceeded', "
        "'persist_failed'"
        "))"
    )


def downgrade() -> None:
    _exec("DROP INDEX IF EXISTS ix_fact_listing_is_active")
    _exec(
        "ALTER TABLE fact_listing DROP COLUMN IF EXISTS is_active"
    )
    _exec(
        "ALTER TABLE fact_listing DROP COLUMN IF EXISTS last_price_changed_at"
    )
    _exec(
        "ALTER TABLE scrape_logs DROP CONSTRAINT IF EXISTS ck_scrape_logs_status"
    )
    _exec(
        "ALTER TABLE scrape_logs DROP CONSTRAINT IF EXISTS scrape_logs_status_check"
    )
    _exec(
        "ALTER TABLE scrape_logs ADD CONSTRAINT ck_scrape_logs_status "
        "CHECK (status IN ("
        "'success', 'error', 'timeout', 'blocked', 'captcha', "
        "'not_found', 'price_not_found', 'parse_error', 'missing_critical_data', "
        "'technical_error', 'fetch_failed', 'parse_failed', 'quota_exceeded', "
        "'persist_failed'"
        "))"
    )
