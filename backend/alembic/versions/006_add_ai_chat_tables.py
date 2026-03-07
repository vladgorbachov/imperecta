"""Add AI chat sessions and messages tables.

Revision ID: 006_ai_chat_tables
Revises: 005_last_login_at
Create Date: 2026-03-06

Idempotent: tables may exist from create_all or partial run.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006_ai_chat_tables"
down_revision: Union[str, None] = "005_last_login_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(connection, name: str) -> bool:
    return inspect(connection).has_table(name)


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "ai_chat_sessions"):
        op.create_table(
            "ai_chat_sessions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
            ),
            sa.Column("title", sa.String(255), nullable=True),
            sa.Column("context_type", sa.String(50), nullable=True),
            sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_ai_chat_sessions_user_id",
            "ai_chat_sessions",
            ["user_id"],
            unique=False,
        )

    if not _table_exists(conn, "ai_chat_messages"):
        op.create_table(
            "ai_chat_messages",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("tokens_used", sa.Integer(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["session_id"],
                ["ai_chat_sessions.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_ai_chat_messages_session_id",
            "ai_chat_messages",
            ["session_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_ai_chat_messages_session_id", table_name="ai_chat_messages")
    op.drop_table("ai_chat_messages")
    op.drop_index("ix_ai_chat_sessions_user_id", table_name="ai_chat_sessions")
    op.drop_table("ai_chat_sessions")
