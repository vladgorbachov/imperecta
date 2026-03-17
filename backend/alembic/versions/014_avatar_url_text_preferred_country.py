"""Avatar URL Text (already applied in 010). Preferred country in schema.

Revision ID: 014_avatar_url_text
Revises: 013_markets_refresh_metadata
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "014_avatar_url_text"
down_revision: Union[str, None] = "013_markets_refresh_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # avatar_url: ensure Text for base64 data URLs (50k+ chars).
    # Migration 010 changed String(2048)->Text. This covers String(5000)->Text if present.
    pass


def downgrade() -> None:
    pass
