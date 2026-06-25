"""Add reject_data.operation for CUD reject attribution.

Revision ID: 029_reject_data_operation
Revises: 028_add_fact_listing_page_role
Create Date: 2026-06-17
"""

from alembic import op

revision = "029_reject_data_operation"
down_revision = "028_add_fact_listing_page_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE reject_data "
        "ADD COLUMN IF NOT EXISTS operation VARCHAR(10) NOT NULL DEFAULT 'insert'"
    )
    op.execute(
        "ALTER TABLE reject_data ADD CONSTRAINT ck_reject_data_operation "
        "CHECK (operation IN ('insert', 'update', 'delete'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE reject_data DROP CONSTRAINT IF EXISTS ck_reject_data_operation")
    op.execute("ALTER TABLE reject_data DROP COLUMN IF EXISTS operation")
