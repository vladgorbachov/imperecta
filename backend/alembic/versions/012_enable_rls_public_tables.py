"""Enable RLS on public application tables (defense in depth for Supabase API keys).

Revision ID: 012_enable_rls_public_tables
Revises: 011_dedup_and_listing_lifecycle
Create Date: 2026-05-28
"""

from alembic import op

revision = "012_enable_rls_public_tables"
down_revision = "011_dedup_and_listing_lifecycle"
branch_labels = None
depends_on = None

# Tables exposed via Supabase; backend uses direct Postgres (table owner bypasses RLS).
_RLS_TABLES = (
    "user_subscriptions",
    "dim_date",
    "dim_currency",
    "dim_category",
    "data_exports",
    "dim_country",
    "fact_currency_rate",
    "fact_crypto_price",
    "fact_commodity_price",
    "dim_marketplace",
    "dim_brand",
    "fact_tariff",
    "fact_fuel_price",
    "dim_product",
    "dim_seller",
    "scrape_jobs",
    "user_products",
    "fact_listing",
    "fact_search_trend",
    "fact_price",
    "fact_review",
    "fact_stock",
    "fact_promo",
    "alerts",
    "alert_events",
    "digests",
    "ai_chat_sessions",
    "ai_chat_messages",
    "api_logs",
    "scrape_logs",
)


def _exec(sql: str) -> None:
    op.execute(sql)


def upgrade() -> None:
    for table in _RLS_TABLES:
        _exec(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        _exec(
            f"DROP POLICY IF EXISTS rls_deny_client_roles ON {table}"
        )
        _exec(
            f"""
            CREATE POLICY rls_deny_client_roles ON {table}
            FOR ALL
            TO anon, authenticated
            USING (false)
            WITH CHECK (false)
            """
        )


def downgrade() -> None:
    for table in reversed(_RLS_TABLES):
        _exec(f"DROP POLICY IF EXISTS rls_deny_client_roles ON {table}")
        _exec(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
