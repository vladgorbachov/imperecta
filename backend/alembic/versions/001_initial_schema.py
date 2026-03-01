"""Initial schema placeholder. Tables are created by app lifespan (create_all).

Revision ID: 001_initial
Revises:
Create Date: 2025-03-01

Avoids running create_all inside Alembic (Supabase pooler/connection quirks).
"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: tables created by FastAPI lifespan (Base.metadata.create_all)."""
    pass


def downgrade() -> None:
    """No-op."""
    pass
