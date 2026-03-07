"""Add last_login_at to users.

Revision ID: 005_last_login_at
Revises: 004_superuser_scrape_admin_api
Create Date: 2026-03-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_last_login_at"
down_revision: Union[str, None] = "004_superuser_scrape_admin_api"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
