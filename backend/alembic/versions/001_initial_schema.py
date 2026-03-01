"""Initial schema: create all tables from models.

Revision ID: 001_initial
Revises:
Create Date: 2025-03-01

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables from app.models (same as Base.metadata.create_all)."""
    from app.database import Base
    from app import models  # noqa: F401 - register all models on Base.metadata

    connection = op.get_bind()
    Base.metadata.create_all(bind=connection)


def downgrade() -> None:
    """Drop all tables."""
    from app.database import Base
    from app import models  # noqa: F401

    connection = op.get_bind()
    Base.metadata.drop_all(bind=connection)
