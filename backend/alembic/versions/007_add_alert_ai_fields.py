"""Add AI fields to alert_events.

Revision ID: 007_alert_ai_fields
Revises: 007_performance_indexes
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_alert_ai_fields"
down_revision: Union[str, None] = "007_performance_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "alert_events",
        sa.Column("severity", sa.String(20), nullable=True),
    )
    op.add_column(
        "alert_events",
        sa.Column("ai_explanation", sa.Text(), nullable=True),
    )
    op.add_column(
        "alert_events",
        sa.Column("ai_recommendation", sa.Text(), nullable=True),
    )
    op.add_column(
        "alert_events",
        sa.Column("ai_recommended_price", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alert_events", "ai_recommended_price")
    op.drop_column("alert_events", "ai_recommendation")
    op.drop_column("alert_events", "ai_explanation")
    op.drop_column("alert_events", "severity")
