"""Add provider_source, country_scope to markets_refresh_log; add fuel to enum.

Revision ID: 013_markets_refresh_metadata
Revises: 012_markets_tables
Create Date: 2026-03-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "013_markets_refresh_metadata"
down_revision: Union[str, None] = "012_markets_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "markets_refresh_log",
        sa.Column("provider_source", sa.String(100), nullable=True),
    )
    op.add_column(
        "markets_refresh_log",
        sa.Column("country_scope", sa.String(10), nullable=True),
    )
    op.execute("ALTER TYPE marketsrefreshtype ADD VALUE IF NOT EXISTS 'fuel'")


def downgrade() -> None:
    op.drop_column("markets_refresh_log", "provider_source")
    op.drop_column("markets_refresh_log", "country_scope")
    # PostgreSQL does not support removing enum values; fuel remains in type
