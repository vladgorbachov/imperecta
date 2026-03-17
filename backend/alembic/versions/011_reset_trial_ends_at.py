"""Reset trial_ends_at for all users.

Revision ID: 011_trial_reset
Revises: 010_avatar_url_extend
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op

revision: str = "011_trial_reset"
down_revision: Union[str, None] = "010_avatar_url_extend"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE users SET trial_ends_at = NULL")


def downgrade() -> None:
    """Cannot restore previous trial_ends_at values."""
    pass
