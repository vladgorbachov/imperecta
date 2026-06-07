"""scrape_jobs parent_job_id.

Revision ID: 020_scrape_jobs_parent_job_id
Revises: 019_scrape_jobs_status_allow_partial
Create Date: 2026-06-07

Rationale: O1 of the γ-full orchestrator redesign. Each marketplace will
become a separate child Celery task that owns its own ScrapeJob row; the
orchestrator tick aggregates children by `parent_job_id`. Add the column
additively (nullable) with a self-referential FK ON DELETE SET NULL and a
composite (parent_job_id, status) index that the tick query will hit.
Legacy callers (monolithic FullPipelineOrchestrator, standalone discover())
do not set parent_job_id and remain unaffected.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "020_scrape_jobs_parent_job_id"
down_revision = "019_scrape_jobs_status_allow_partial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scrape_jobs",
        sa.Column(
            "parent_job_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_scrape_jobs_parent_job_id",
        source_table="scrape_jobs",
        referent_table="scrape_jobs",
        local_cols=["parent_job_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_scrape_jobs_parent_status",
        "scrape_jobs",
        ["parent_job_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_scrape_jobs_parent_status", table_name="scrape_jobs")
    op.drop_constraint(
        "fk_scrape_jobs_parent_job_id", "scrape_jobs", type_="foreignkey"
    )
    op.drop_column("scrape_jobs", "parent_job_id")
