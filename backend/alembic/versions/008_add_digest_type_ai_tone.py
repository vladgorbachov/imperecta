"""Add ai_tone to users, extend digest period_type for strategic.

Revision ID: 008_digest_ai_tone
Revises: 007_alert_ai_fields
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008_digest_ai_tone"
down_revision: Union[str, None] = "007_alert_ai_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("ai_tone", sa.String(20), nullable=False, server_default="balanced"),
    )
    op.alter_column(
        "digests",
        "period_type",
        existing_type=sa.String(10),
        type_=sa.String(20),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.drop_column("users", "ai_tone")
    op.alter_column(
        "digests",
        "period_type",
        existing_type=sa.String(20),
        type_=sa.String(10),
        existing_nullable=False,
    )
