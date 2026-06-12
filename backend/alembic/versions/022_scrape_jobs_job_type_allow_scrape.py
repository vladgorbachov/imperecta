"""scrape_jobs job_type allow scrape.

Revision ID: 022_scrape_jobs_job_type_allow_scrape
Revises: 021_fact_listing_failure_streak
Create Date: 2026-06-12

Rationale: O4 makes scrape a per-marketplace child task
(scrape_one_marketplace) that owns a ScrapeJob row with job_type='scrape'.
The existing ck_scrape_jobs_job_type CHECK does not allow 'scrape', so the
first child insert would be rejected. Add 'scrape' as a first-class job_type.
Single statement per op.
"""

from alembic import op

revision = "022_scrape_jobs_job_type_allow_scrape"
down_revision = "021_fact_listing_failure_streak"
branch_labels = None
depends_on = None

_ALLOWED_WITH_SCRAPE = (
    "'scheduled','manual','retry','backfill','discovery',"
    "'full_pipeline_test','scrape'"
)
_ALLOWED_WITHOUT_SCRAPE = (
    "'scheduled','manual','retry','backfill','discovery','full_pipeline_test'"
)


def upgrade() -> None:
    op.drop_constraint("ck_scrape_jobs_job_type", "scrape_jobs", type_="check")
    op.create_check_constraint(
        "ck_scrape_jobs_job_type",
        "scrape_jobs",
        f"job_type IN ({_ALLOWED_WITH_SCRAPE})",
    )


def downgrade() -> None:
    # Collapse any 'scrape' rows to status='cancelled' BEFORE restoring the
    # stricter constraint. Mirrors 019's data-safety approach: never delete
    # rows. status='cancelled' is already a valid status.
    op.execute(
        "UPDATE scrape_jobs SET status = 'cancelled' "
        "WHERE job_type = 'scrape'"
    )
    op.drop_constraint("ck_scrape_jobs_job_type", "scrape_jobs", type_="check")
    op.create_check_constraint(
        "ck_scrape_jobs_job_type",
        "scrape_jobs",
        f"job_type IN ({_ALLOWED_WITHOUT_SCRAPE})",
    )
