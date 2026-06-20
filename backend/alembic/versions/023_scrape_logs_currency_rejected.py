"""scrape_logs status allow currency_rejected.

Revision ID: 023_scrape_logs_currency_rejected
Revises: 022_scrape_jobs_job_type_allow_scrape
Create Date: 2026-06-19

Rationale: D1-A+C labels currency gate rejections honestly as currency_rejected
instead of parse_error. Extend ck_scrape_logs_status CHECK additively.
"""

from alembic import op

revision = "023_scrape_logs_currency_rejected"
down_revision = "022_scrape_jobs_job_type_allow_scrape"
branch_labels = None
depends_on = None

_STATUSES_WITH_CURRENCY_REJECTED = (
    "'success', 'no_change', 'error', 'timeout', 'blocked', 'captcha', "
    "'not_found', 'price_not_found', 'parse_error', 'currency_rejected', "
    "'missing_critical_data', 'technical_error', 'fetch_failed', "
    "'parse_failed', 'quota_exceeded', 'persist_failed'"
)

_STATUSES_WITHOUT_CURRENCY_REJECTED = (
    "'success', 'no_change', 'error', 'timeout', 'blocked', 'captcha', "
    "'not_found', 'price_not_found', 'parse_error', 'missing_critical_data', "
    "'technical_error', 'fetch_failed', 'parse_failed', 'quota_exceeded', "
    "'persist_failed'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE scrape_logs DROP CONSTRAINT IF EXISTS ck_scrape_logs_status")
    op.execute(
        "ALTER TABLE scrape_logs DROP CONSTRAINT IF EXISTS scrape_logs_status_check"
    )
    op.execute(
        "ALTER TABLE scrape_logs ADD CONSTRAINT ck_scrape_logs_status "
        f"CHECK (status IN ({_STATUSES_WITH_CURRENCY_REJECTED}))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE scrape_logs DROP CONSTRAINT IF EXISTS ck_scrape_logs_status")
    op.execute(
        "ALTER TABLE scrape_logs DROP CONSTRAINT IF EXISTS scrape_logs_status_check"
    )
    op.execute(
        "ALTER TABLE scrape_logs ADD CONSTRAINT ck_scrape_logs_status "
        f"CHECK (status IN ({_STATUSES_WITHOUT_CURRENCY_REJECTED}))"
    )
