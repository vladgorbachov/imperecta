"""Trim dim_date preseed to deploy-time cutoff (2026-06-27).

Revision ID: 037_trim_dim_date_preseed
Revises: 036_dim_marketplace_phase1_exhausted_streak
Create Date: 2026-06-27

FK-safe at authoring time: all nine dim_date FK sources (fact_currency_rate,
fact_crypto_price, fact_commodity_price, fact_price + partitions,
fact_promo.start_date_id + end_date_id, fact_review, fact_search_trend,
fact_fuel_price) had zero references to date_id > 20260627.

Purpose: stop preseeding the calendar through 2030 so _ensure_dim_date inserts
dates through the data_firewall gate as market-data ingest advances.
"""

from alembic import op

revision = "037_trim_dim_date_preseed"
down_revision = "036_dim_marketplace_phase1_exhausted_streak"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM dim_date WHERE date_id > 20260627")


def downgrade() -> None:
    # Not reversible: deleted rows were a static preseed (2024–2030).
    # Calendar rows beyond the trim boundary are rebuilt by gate inserts on ingest.
