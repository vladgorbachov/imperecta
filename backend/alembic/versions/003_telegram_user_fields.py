"""Add telegram_chat_id unique constraint and telegram_link_code size.

Revision ID: 003_telegram_user_fields
Revises: 002_update_user_language
Create Date: 2025-03-04

Changes:
- telegram_chat_id: add unique constraint
- telegram_link_code: VARCHAR(20) -> VARCHAR(6)
"""
from typing import Sequence, Union

from alembic import op


revision: str = "003_telegram_user_fields"
down_revision: Union[str, None] = "002_update_user_language"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique to telegram_chat_id, resize telegram_link_code."""
    # Clear link codes longer than 6 chars before resize
    op.execute(
        "UPDATE users SET telegram_link_code = NULL "
        "WHERE telegram_link_code IS NOT NULL AND LENGTH(telegram_link_code) > 6"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN telegram_link_code TYPE VARCHAR(6)"
    )
    # Clear duplicate chat_ids before adding unique (keep first occurrence)
    op.execute(
        """
        UPDATE users SET telegram_chat_id = NULL
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                    ROW_NUMBER() OVER (PARTITION BY telegram_chat_id ORDER BY id) AS rn
                FROM users
                WHERE telegram_chat_id IS NOT NULL
            ) sub
            WHERE sub.rn > 1
        )
        """
    )
    op.create_unique_constraint(
        "uq_users_telegram_chat_id",
        "users",
        ["telegram_chat_id"],
    )


def downgrade() -> None:
    """Remove unique, revert telegram_link_code size."""
    op.drop_constraint("uq_users_telegram_chat_id", "users", type_="unique")
    op.execute(
        "ALTER TABLE users ALTER COLUMN telegram_link_code TYPE VARCHAR(20)"
    )
