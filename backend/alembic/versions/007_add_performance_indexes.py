"""Add performance indexes for production load.

Revision ID: 007_performance_indexes
Revises: 006_ai_chat_tables
Create Date: 2026-03-06

Idempotent: indexes may exist from partial run or create_all.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "007_performance_indexes"
down_revision: Union[str, None] = "006_ai_chat_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # price_snapshots: replace single-column indexes with composite + date
    # Use IF EXISTS for idempotency (indexes may not exist if create_all used current model)
    op.execute(
        "DROP INDEX IF EXISTS ix_price_snapshots_competitor_product_id"
    )
    op.execute("DROP INDEX IF EXISTS ix_price_snapshots_scraped_at")
    op.create_index(
        "ix_snapshots_cp_date",
        "price_snapshots",
        ["competitor_product_id", "scraped_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_snapshots_date",
        "price_snapshots",
        ["scraped_at"],
        if_not_exists=True,
    )

    # alert_events: add indexes for triggered_at queries
    op.create_index(
        "ix_alert_events_triggered",
        "alert_events",
        ["triggered_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_alert_events_alert_triggered",
        "alert_events",
        ["alert_id", "triggered_at"],
        if_not_exists=True,
    )

    # scrape_logs: rename marketplace index and add status index
    op.execute("DROP INDEX IF EXISTS ix_scrape_logs_marketplace_created")
    op.create_index(
        "ix_scrape_logs_mp_date",
        "scrape_logs",
        ["marketplace_id", "created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_scrape_logs_status",
        "scrape_logs",
        ["status", "created_at"],
        if_not_exists=True,
    )

    # ai_chat_messages: add composite index for session + created_at
    op.create_index(
        "ix_chat_messages_session",
        "ai_chat_messages",
        ["session_id", "created_at"],
        if_not_exists=True,
    )

    # api_logs: add composite index for service + created_at
    op.create_index(
        "ix_api_logs_service_date",
        "api_logs",
        ["service", "created_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    # api_logs
    op.execute("DROP INDEX IF EXISTS ix_api_logs_service_date")

    # ai_chat_messages
    op.execute("DROP INDEX IF EXISTS ix_chat_messages_session")

    # scrape_logs
    op.execute("DROP INDEX IF EXISTS ix_scrape_logs_status")
    op.execute("DROP INDEX IF EXISTS ix_scrape_logs_mp_date")
    op.create_index(
        "ix_scrape_logs_marketplace_created",
        "scrape_logs",
        ["marketplace_id", "created_at"],
    )

    # alert_events
    op.execute("DROP INDEX IF EXISTS ix_alert_events_alert_triggered")
    op.execute("DROP INDEX IF EXISTS ix_alert_events_triggered")

    # price_snapshots
    op.execute("DROP INDEX IF EXISTS ix_snapshots_date")
    op.execute("DROP INDEX IF EXISTS ix_snapshots_cp_date")
    op.create_index(
        "ix_price_snapshots_competitor_product_id",
        "price_snapshots",
        ["competitor_product_id"],
    )
    op.create_index("ix_price_snapshots_scraped_at", "price_snapshots", ["scraped_at"])
