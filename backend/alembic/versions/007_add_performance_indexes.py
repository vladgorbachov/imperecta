"""Add performance indexes for production load.

Revision ID: 007_performance_indexes
Revises: 006_ai_chat_tables
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op

revision: str = "007_performance_indexes"
down_revision: Union[str, None] = "006_ai_chat_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # price_snapshots: replace single-column indexes with composite + date
    op.drop_index(
        "ix_price_snapshots_competitor_product_id",
        table_name="price_snapshots",
    )
    op.drop_index("ix_price_snapshots_scraped_at", table_name="price_snapshots")
    op.create_index(
        "ix_snapshots_cp_date",
        "price_snapshots",
        ["competitor_product_id", "scraped_at"],
    )
    op.create_index("ix_snapshots_date", "price_snapshots", ["scraped_at"])

    # alert_events: add indexes for triggered_at queries
    op.create_index(
        "ix_alert_events_triggered",
        "alert_events",
        ["triggered_at"],
    )
    op.create_index(
        "ix_alert_events_alert_triggered",
        "alert_events",
        ["alert_id", "triggered_at"],
    )

    # scrape_logs: rename marketplace index and add status index
    op.drop_index(
        "ix_scrape_logs_marketplace_created",
        table_name="scrape_logs",
    )
    op.create_index(
        "ix_scrape_logs_mp_date",
        "scrape_logs",
        ["marketplace_id", "created_at"],
    )
    op.create_index(
        "ix_scrape_logs_status",
        "scrape_logs",
        ["status", "created_at"],
    )

    # ai_chat_messages: add composite index for session + created_at
    op.create_index(
        "ix_chat_messages_session",
        "ai_chat_messages",
        ["session_id", "created_at"],
    )

    # api_logs: add composite index for service + created_at
    op.create_index(
        "ix_api_logs_service_date",
        "api_logs",
        ["service", "created_at"],
    )


def downgrade() -> None:
    # api_logs
    op.drop_index("ix_api_logs_service_date", table_name="api_logs")

    # ai_chat_messages
    op.drop_index("ix_chat_messages_session", table_name="ai_chat_messages")

    # scrape_logs
    op.drop_index("ix_scrape_logs_status", table_name="scrape_logs")
    op.drop_index("ix_scrape_logs_mp_date", table_name="scrape_logs")
    op.create_index(
        "ix_scrape_logs_marketplace_created",
        "scrape_logs",
        ["marketplace_id", "created_at"],
    )

    # alert_events
    op.drop_index("ix_alert_events_alert_triggered", table_name="alert_events")
    op.drop_index("ix_alert_events_triggered", table_name="alert_events")

    # price_snapshots
    op.drop_index("ix_snapshots_date", table_name="price_snapshots")
    op.drop_index("ix_snapshots_cp_date", table_name="price_snapshots")
    op.create_index(
        "ix_price_snapshots_competitor_product_id",
        "price_snapshots",
        ["competitor_product_id"],
    )
    op.create_index("ix_price_snapshots_scraped_at", "price_snapshots", ["scraped_at"])
