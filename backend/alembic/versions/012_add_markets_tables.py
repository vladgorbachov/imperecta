"""Add markets domain tables: preferences, refresh log, snapshots, overview, analytics, opportunities.

Revision ID: 012_markets_tables
Revises: 011_trial_reset
Create Date: 2026-03-12

Supports scheduled snapshot refreshes every 2 hours.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "012_markets_tables"
down_revision: Union[str, None] = "011_trial_reset"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "markets_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("preferred_country_code", sa.String(3), nullable=True),
        sa.Column("favorite_instrument_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
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
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "markets_refresh_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "refresh_type",
            sa.Enum("forex", "crypto", "commodities", "ticker", "overview", "category", "marketplace", "opportunities", name="marketsrefreshtype"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "success", "error", name="marketsrefreshstatus"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "markets_forex",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("bid", sa.Numeric(18, 6), nullable=False),
        sa.Column("ask", sa.Numeric(18, 6), nullable=False),
        sa.Column("spread", sa.Numeric(10, 6), nullable=False),
        sa.Column("change_24h", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_markets_forex_symbol", "markets_forex", ["symbol"], unique=True)

    op.create_table(
        "markets_crypto",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("change_24h", sa.Numeric(10, 4), nullable=True),
        sa.Column("market_cap", sa.Numeric(24, 2), nullable=True),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_markets_crypto_symbol", "markets_crypto", ["symbol"], unique=True)

    op.create_table(
        "markets_commodities",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("change_24h", sa.Numeric(10, 4), nullable=True),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_markets_commodities_symbol", "markets_commodities", ["symbol"], unique=True)

    op.create_table(
        "markets_ticker",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("price", sa.Numeric(24, 4), nullable=False),
        sa.Column("change_24h", sa.Numeric(10, 4), nullable=True),
        sa.Column("currency", sa.String(5), nullable=True),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_markets_ticker_symbol", "markets_ticker", ["symbol"], unique=True)

    op.create_table(
        "markets_overview",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("marketplace", sa.String(50), nullable=False),
        sa.Column("marketplace_domain", sa.String(255), nullable=False, server_default=""),
        sa.Column("product_name", sa.String(500), nullable=False),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(5), nullable=False, server_default="RUB"),
        sa.Column("change_24h", sa.Numeric(10, 4), nullable=True),
        sa.Column("change_3d", sa.Numeric(10, 4), nullable=True),
        sa.Column("change_1w", sa.Numeric(10, 4), nullable=True),
        sa.Column("change_1m", sa.Numeric(10, 4), nullable=True),
        sa.Column("sparkline_data", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_markets_overview_marketplace", "markets_overview", ["marketplace"])
    op.create_index("ix_markets_overview_refreshed", "markets_overview", ["refreshed_at"])

    op.create_table(
        "markets_category_analytics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", sa.String(100), nullable=False),
        sa.Column("segment", sa.String(100), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_markets_category_id", "markets_category_analytics", ["category_id"])
    op.create_index("ix_markets_category_refreshed", "markets_category_analytics", ["refreshed_at"])

    op.create_table(
        "markets_marketplace_analytics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("marketplace_id", sa.String(50), nullable=False),
        sa.Column("marketplace_name", sa.String(100), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_markets_marketplace_id", "markets_marketplace_analytics", ["marketplace_id"])
    op.create_index("ix_markets_marketplace_refreshed", "markets_marketplace_analytics", ["refreshed_at"])

    op.create_table(
        "markets_opportunities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("block_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_markets_opportunities_type", "markets_opportunities", ["block_type"])
    op.create_index("ix_markets_opportunities_refreshed", "markets_opportunities", ["refreshed_at"])


def downgrade() -> None:
    op.drop_index("ix_markets_opportunities_refreshed", table_name="markets_opportunities")
    op.drop_index("ix_markets_opportunities_type", table_name="markets_opportunities")
    op.drop_table("markets_opportunities")

    op.drop_index("ix_markets_marketplace_refreshed", table_name="markets_marketplace_analytics")
    op.drop_index("ix_markets_marketplace_id", table_name="markets_marketplace_analytics")
    op.drop_table("markets_marketplace_analytics")

    op.drop_index("ix_markets_category_refreshed", table_name="markets_category_analytics")
    op.drop_index("ix_markets_category_id", table_name="markets_category_analytics")
    op.drop_table("markets_category_analytics")

    op.drop_index("ix_markets_overview_refreshed", table_name="markets_overview")
    op.drop_index("ix_markets_overview_marketplace", table_name="markets_overview")
    op.drop_table("markets_overview")

    op.drop_index("ix_markets_ticker_symbol", table_name="markets_ticker")
    op.drop_table("markets_ticker")

    op.drop_index("ix_markets_commodities_symbol", table_name="markets_commodities")
    op.drop_table("markets_commodities")

    op.drop_index("ix_markets_crypto_symbol", table_name="markets_crypto")
    op.drop_table("markets_crypto")

    op.drop_index("ix_markets_forex_symbol", table_name="markets_forex")
    op.drop_table("markets_forex")

    op.drop_table("markets_refresh_log")
    op.drop_table("markets_preferences")

    op.execute("DROP TYPE IF EXISTS marketsrefreshtype")
    op.execute("DROP TYPE IF EXISTS marketsrefreshstatus")
