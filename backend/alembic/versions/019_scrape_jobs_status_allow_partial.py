"""scrape_jobs status allow partial.

Revision ID: 019_scrape_jobs_status_allow_partial
Revises: 018_dim_marketplace_category_resume_index
Create Date: 2026-06-07

Rationale: discover() writes job.status='partial' for inner discovery jobs
on partial_budget outcomes (resumable sitemap/category paths). The existing
CHECK constraint ck_scrape_jobs_status only allows
('pending','running','completed','failed','cancelled'), so the first real
partial outcome rejects the commit and leaves the inner job stuck running.
Make 'partial' a first-class valid status. Single statement per op.
"""

from alembic import op

revision = "019_scrape_jobs_status_allow_partial"
down_revision = "018_dim_marketplace_category_resume_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_scrape_jobs_status", "scrape_jobs", type_="check")
    op.create_check_constraint(
        "ck_scrape_jobs_status",
        "scrape_jobs",
        "status IN ('pending','running','completed','failed','cancelled','partial')",
    )


def downgrade() -> None:
    # Collapse any 'partial' rows to 'failed' BEFORE restoring the stricter
    # constraint, else the recreate would fail on existing data.
    op.execute(
        "UPDATE scrape_jobs SET status = 'failed' WHERE status = 'partial'"
    )
    op.drop_constraint("ck_scrape_jobs_status", "scrape_jobs", type_="check")
    op.create_check_constraint(
        "ck_scrape_jobs_status",
        "scrape_jobs",
        "status IN ('pending','running','completed','failed','cancelled')",
    )
