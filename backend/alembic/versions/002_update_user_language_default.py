"""Update user language column default and size.

Revision ID: 002_update_user_language
Revises: 001_initial
Create Date: 2025-03-04

Changes:
- language: default 'ru' -> 'en'
- language: String(10) -> String(5)
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "002_update_user_language"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Alter users.language: default 'en', type VARCHAR(5)."""
    op.execute(
        "ALTER TABLE users ALTER COLUMN language TYPE VARCHAR(5), "
        "ALTER COLUMN language SET DEFAULT 'en'"
    )


def downgrade() -> None:
    """Revert language column to default 'ru', type VARCHAR(10)."""
    op.execute(
        "ALTER TABLE users ALTER COLUMN language TYPE VARCHAR(10), "
        "ALTER COLUMN language SET DEFAULT 'ru'"
    )
