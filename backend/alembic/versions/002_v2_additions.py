"""V2 additions: crypto, commodity, fuel tables + marketplace discovery fields + fixes."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "002_v2_additions"
down_revision = "001_v2_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- A1: fact_crypto_price ---
    op.create_table(
        "fact_crypto_price",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("date_id", sa.Integer(), sa.ForeignKey("dim_date.date_id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("price_usd", sa.Numeric(18, 8), nullable=False),
        sa.Column("price_eur", sa.Numeric(18, 8), nullable=True),
        sa.Column("market_cap_usd", sa.Numeric(20, 2), nullable=True),
        sa.Column("volume_24h_usd", sa.Numeric(20, 2), nullable=True),
        sa.Column("change_1h_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("change_24h_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("change_7d_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("high_24h_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("low_24h_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("circulating_supply", sa.Numeric(20, 2), nullable=True),
        sa.Column("total_supply", sa.Numeric(20, 2), nullable=True),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("date_id", "symbol", "source", name="uq_crypto_date_symbol_source"),
        sa.CheckConstraint(
            "source IN ('binance','coingecko','coinmarketcap','custom')",
            name="ck_crypto_source",
        ),
    )
    op.create_index("idx_crypto_date", "fact_crypto_price", ["date_id"])
    op.create_index("idx_crypto_symbol", "fact_crypto_price", ["symbol"])
    op.create_index("idx_crypto_date_symbol", "fact_crypto_price", ["date_id", "symbol"])

    # --- A2: fact_commodity_price ---
    op.create_table(
        "fact_commodity_price",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("date_id", sa.Integer(), sa.ForeignKey("dim_date.date_id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("commodity_type", sa.String(20), nullable=False),
        sa.Column("price_usd", sa.Numeric(12, 4), nullable=False),
        sa.Column("price_eur", sa.Numeric(12, 4), nullable=True),
        sa.Column("change_24h_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("change_7d_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("date_id", "symbol", "source", name="uq_commodity_date_symbol_source"),
        sa.CheckConstraint(
            "commodity_type IN ('metal','energy','agricultural')",
            name="ck_commodity_type",
        ),
        sa.CheckConstraint(
            "source IN ('goldapi','alpha_vantage','eia','custom')",
            name="ck_commodity_source",
        ),
    )
    op.create_index("idx_commodity_date", "fact_commodity_price", ["date_id"])
    op.create_index("idx_commodity_symbol", "fact_commodity_price", ["symbol"])
    op.create_index("idx_commodity_date_symbol", "fact_commodity_price", ["date_id", "symbol"])

    # --- A3: fact_fuel_price ---
    op.create_table(
        "fact_fuel_price",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("date_id", sa.Integer(), sa.ForeignKey("dim_date.date_id"), nullable=False),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("dim_country.country_code"), nullable=False),
        sa.Column("fuel_type", sa.String(20), nullable=False),
        sa.Column("price_local", sa.Numeric(8, 4), nullable=False),
        sa.Column("currency_code", sa.String(3), sa.ForeignKey("dim_currency.currency_code"), nullable=False),
        sa.Column("price_eur", sa.Numeric(8, 4), nullable=True),
        sa.Column("change_week_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("change_month_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "date_id",
            "country_code",
            "fuel_type",
            "source",
            name="uq_fuel_date_country_type_source",
        ),
        sa.CheckConstraint(
            "fuel_type IN ("
            "'gasoline_92','gasoline_95','gasoline_98','gasoline_100',"
            "'diesel','diesel_premium','lpg','cng','electricity'"
            ")",
            name="ck_fuel_type",
        ),
    )
    op.create_index("idx_fuel_date", "fact_fuel_price", ["date_id"])
    op.create_index("idx_fuel_country", "fact_fuel_price", ["country_code"])
    op.create_index(
        "idx_fuel_date_country_type",
        "fact_fuel_price",
        ["date_id", "country_code", "fuel_type"],
    )

    # --- B: dim_marketplace discovery fields ---
    op.add_column("dim_marketplace", sa.Column("product_quota", sa.Integer(), server_default=sa.text("0")))
    op.add_column("dim_marketplace", sa.Column("products_in_pool", sa.Integer(), server_default=sa.text("0")))
    op.add_column("dim_marketplace", sa.Column("requires_js", sa.Boolean(), server_default=sa.text("false")))
    op.add_column(
        "dim_marketplace",
        sa.Column("rate_limit_delay", sa.Numeric(4, 1), server_default=sa.text("2.0")),
    )
    op.add_column("dim_marketplace", sa.Column("custom_product_link_selector", sa.Text(), nullable=True))
    op.add_column("dim_marketplace", sa.Column("custom_next_page_selector", sa.Text(), nullable=True))
    op.add_column("dim_marketplace", sa.Column("custom_price_selector", sa.Text(), nullable=True))
    op.add_column("dim_marketplace", sa.Column("custom_title_selector", sa.Text(), nullable=True))
    op.add_column("dim_marketplace", sa.Column("last_discovery_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("dim_marketplace", sa.Column("last_discovery_status", sa.String(20), nullable=True))
    op.add_column(
        "dim_marketplace",
        sa.Column("last_discovery_products_found", sa.Integer(), server_default=sa.text("0")),
    )
    op.add_column(
        "dim_marketplace",
        sa.Column("discovery_error_count", sa.Integer(), server_default=sa.text("0")),
    )

    # --- C: fact_listing url_hash ---
    op.add_column("fact_listing", sa.Column("url_hash", sa.String(64), nullable=True))
    op.create_index("idx_listing_url_hash", "fact_listing", ["url_hash"], unique=True)

    # --- D: users preferences JSONB ---
    op.add_column(
        "users",
        sa.Column(
            "preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    # --- E: Fix dim_date week_iso (calendar week, not ISO DOW) ---
    op.execute(sa.text("UPDATE dim_date SET week_iso = EXTRACT(WEEK FROM full_date)::SMALLINT"))

    # --- F: Extension not available on Supabase managed Postgres ---
    op.execute(sa.text("DROP EXTENSION IF EXISTS jsonb_plperl"))


def downgrade() -> None:
    op.drop_column("users", "preferences")

    op.drop_index("idx_listing_url_hash", table_name="fact_listing")
    op.drop_column("fact_listing", "url_hash")

    for col in (
        "discovery_error_count",
        "last_discovery_products_found",
        "last_discovery_status",
        "last_discovery_at",
        "custom_title_selector",
        "custom_price_selector",
        "custom_next_page_selector",
        "custom_product_link_selector",
        "rate_limit_delay",
        "requires_js",
        "products_in_pool",
        "product_quota",
    ):
        op.drop_column("dim_marketplace", col)

    op.drop_table("fact_fuel_price")
    op.drop_table("fact_commodity_price")
    op.drop_table("fact_crypto_price")
