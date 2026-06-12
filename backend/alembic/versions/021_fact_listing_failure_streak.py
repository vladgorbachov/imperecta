"""fact_listing failure_streak (persistent deactivation counter).

Revision ID: 021_fact_listing_failure_streak
Revises: 020_scrape_jobs_parent_job_id
Create Date: 2026-06-11

Rationale: scrape_product() now resets consecutive_errors/last_error
pre-flight (a fresh attempt must not carry a prior run's error). That made
consecutive_errors unusable as the circuit-breaker counter. failure_streak
is the persistent streak that drives listing deactivation
(>= LISTING_DEACTIVATE_AFTER_ERRORS consecutive failures): incremented on
failure, reset to 0 only on success, and NOT reset pre-flight. Backfill from
consecutive_errors so already-problematic listings keep their accrued streak
and are not granted a fresh reprieve before deactivation.
"""

import sqlalchemy as sa
from alembic import op

revision = "021_fact_listing_failure_streak"
down_revision = "020_scrape_jobs_parent_job_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fact_listing",
        sa.Column(
            "failure_streak",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    # Preserve accrued streak; one statement (asyncpg-safe).
    op.execute("UPDATE fact_listing SET failure_streak = consecutive_errors")


def downgrade() -> None:
    op.drop_column("fact_listing", "failure_streak")
