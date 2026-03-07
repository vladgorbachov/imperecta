"""Add avatar_url to users.

Revision ID: 009_avatar_url
Revises: 008_digest_ai_tone
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009_avatar_url"
down_revision: Union[str, None] = "008_digest_ai_tone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("avatar_url", sa.String(2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
