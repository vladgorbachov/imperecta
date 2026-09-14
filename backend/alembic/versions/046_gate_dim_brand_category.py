"""Gate paths for dim_brand / dim_category (parser taxonomy completeness).

Revision ID: 046_gate_dim_brand_category
Revises: 045_grant_app_insert_service_alerts
Create Date: 2026-09-14

Extends the DB-side gate whitelists so scrape enrichment can upsert brand and
category dimensions through gate.exec_write: locator = ('id',), operations =
insert/update (no delete — taxonomy rows are never removed by scrape).
Function bodies mirror 039 verbatim plus the two new WHEN branches.
"""

from __future__ import annotations

from alembic import op

revision = "046_gate_dim_brand_category"
down_revision = "045_grant_app_insert_service_alerts"
branch_labels = None
depends_on = None

_SEARCH_PATH = "SET search_path = pg_catalog, public, extensions, pg_temp"

_LOCATOR_KEYS_BRANCHES = """
                WHEN 'dim_date' THEN RETURN ARRAY['date_id'];
                WHEN 'fact_price' THEN RETURN ARRAY['listing_id', 'date_id'];
                WHEN 'fact_listing' THEN RETURN ARRAY['url_hash'];
                WHEN 'dim_product' THEN RETURN ARRAY['id'];
                WHEN 'dim_marketplace' THEN RETURN ARRAY['id'];
                WHEN 'dim_brand' THEN RETURN ARRAY['id'];
                WHEN 'dim_category' THEN RETURN ARRAY['id'];
                WHEN 'scrape_jobs' THEN RETURN ARRAY['id'];
                WHEN 'fact_currency_rate' THEN RETURN ARRAY['date_id', 'currency_code', 'source'];
                WHEN 'fact_crypto_price' THEN RETURN ARRAY['date_id', 'symbol', 'source'];
                WHEN 'fact_commodity_price' THEN RETURN ARRAY['date_id', 'symbol', 'source'];
                WHEN 'service_alerts' THEN RETURN ARRAY['id'];
                WHEN 'users' THEN RETURN ARRAY['id'];
                WHEN 'ai_chat_sessions' THEN RETURN ARRAY['id'];
                WHEN 'ai_chat_messages' THEN RETURN ARRAY['id'];
                WHEN 'scrape_logs' THEN RETURN ARRAY[]::text[];
                WHEN 'api_logs' THEN RETURN ARRAY[]::text[];
                WHEN 'reject_data' THEN RETURN ARRAY[]::text[];
                ELSE RETURN NULL;
"""

_OPERATION_ALLOWED_BRANCHES = """
                WHEN 'dim_date' THEN RETURN p_operation = 'insert';
                WHEN 'dim_product' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'dim_marketplace' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'dim_brand' THEN RETURN p_operation IN ('insert', 'update');
                WHEN 'dim_category' THEN RETURN p_operation IN ('insert', 'update');
                WHEN 'scrape_jobs' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'fact_listing' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'fact_price' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'fact_currency_rate' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'fact_crypto_price' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'fact_commodity_price' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'scrape_logs' THEN RETURN p_operation IN ('insert', 'retention_delete');
                WHEN 'api_logs' THEN RETURN p_operation IN ('insert', 'retention_delete');
                WHEN 'service_alerts' THEN RETURN p_operation IN ('insert', 'retention_delete');
                WHEN 'reject_data' THEN RETURN p_operation = 'retention_delete';
                WHEN 'users' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'ai_chat_sessions' THEN RETURN p_operation = 'insert';
                WHEN 'ai_chat_messages' THEN RETURN p_operation = 'insert';
                ELSE RETURN FALSE;
"""

_LOCATOR_KEYS_039_BRANCHES = """
                WHEN 'dim_date' THEN RETURN ARRAY['date_id'];
                WHEN 'fact_price' THEN RETURN ARRAY['listing_id', 'date_id'];
                WHEN 'fact_listing' THEN RETURN ARRAY['url_hash'];
                WHEN 'dim_product' THEN RETURN ARRAY['id'];
                WHEN 'dim_marketplace' THEN RETURN ARRAY['id'];
                WHEN 'scrape_jobs' THEN RETURN ARRAY['id'];
                WHEN 'fact_currency_rate' THEN RETURN ARRAY['date_id', 'currency_code', 'source'];
                WHEN 'fact_crypto_price' THEN RETURN ARRAY['date_id', 'symbol', 'source'];
                WHEN 'fact_commodity_price' THEN RETURN ARRAY['date_id', 'symbol', 'source'];
                WHEN 'service_alerts' THEN RETURN ARRAY['id'];
                WHEN 'users' THEN RETURN ARRAY['id'];
                WHEN 'ai_chat_sessions' THEN RETURN ARRAY['id'];
                WHEN 'ai_chat_messages' THEN RETURN ARRAY['id'];
                WHEN 'scrape_logs' THEN RETURN ARRAY[]::text[];
                WHEN 'api_logs' THEN RETURN ARRAY[]::text[];
                WHEN 'reject_data' THEN RETURN ARRAY[]::text[];
                ELSE RETURN NULL;
"""

_OPERATION_ALLOWED_039_BRANCHES = """
                WHEN 'dim_date' THEN RETURN p_operation = 'insert';
                WHEN 'dim_product' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'dim_marketplace' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'scrape_jobs' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'fact_listing' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'fact_price' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'fact_currency_rate' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'fact_crypto_price' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'fact_commodity_price' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'scrape_logs' THEN RETURN p_operation IN ('insert', 'retention_delete');
                WHEN 'api_logs' THEN RETURN p_operation IN ('insert', 'retention_delete');
                WHEN 'service_alerts' THEN RETURN p_operation IN ('insert', 'retention_delete');
                WHEN 'reject_data' THEN RETURN p_operation = 'retention_delete';
                WHEN 'users' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'ai_chat_sessions' THEN RETURN p_operation = 'insert';
                WHEN 'ai_chat_messages' THEN RETURN p_operation = 'insert';
                ELSE RETURN FALSE;
"""


def _locator_keys_fn(branches: str) -> str:
    return f"""
        CREATE OR REPLACE FUNCTION gate._locator_keys(p_table text)
        RETURNS text[]
        LANGUAGE plpgsql
        IMMUTABLE
        {_SEARCH_PATH}
        AS $fn$
        BEGIN
            CASE p_table
{branches}
            END CASE;
        END;
        $fn$;
    """


def _operation_allowed_fn(branches: str) -> str:
    return f"""
        CREATE OR REPLACE FUNCTION gate._operation_allowed(p_table text, p_operation text)
        RETURNS boolean
        LANGUAGE plpgsql
        IMMUTABLE
        {_SEARCH_PATH}
        AS $fn$
        BEGIN
            CASE p_table
{branches}
            END CASE;
        END;
        $fn$;
    """


def upgrade() -> None:
    op.execute(_locator_keys_fn(_LOCATOR_KEYS_BRANCHES))
    op.execute(_operation_allowed_fn(_OPERATION_ALLOWED_BRANCHES))


def downgrade() -> None:
    op.execute(_locator_keys_fn(_LOCATOR_KEYS_039_BRANCHES))
    op.execute(_operation_allowed_fn(_OPERATION_ALLOWED_039_BRANCHES))
