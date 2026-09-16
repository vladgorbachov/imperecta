"""Gate path: allow UPDATE on service_alerts (resolve flow, P9).

Revision ID: 050_service_alerts_update
Revises: 049_gate_alert_events
Create Date: 2026-09-16

The admin panel's Resolve button (frontend P9) marks a service alert as
resolved by setting resolved_at. service_alerts previously allowed only
insert + retention_delete through the gate; this adds 'update'. The Python
side restricts the update payload to {id, resolved_at} (alerts_admin_write),
and function bodies mirror 049 verbatim plus the widened branch.
"""

from __future__ import annotations

from alembic import op

revision = "050_service_alerts_update"
down_revision = "049_gate_alert_events"
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
                WHEN 'alerts' THEN RETURN ARRAY['id'];
                WHEN 'alert_events' THEN RETURN ARRAY[]::text[];
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
                WHEN 'alerts' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'alert_events' THEN RETURN p_operation = 'insert';
                WHEN 'scrape_jobs' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'fact_listing' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'fact_price' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'fact_currency_rate' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'fact_crypto_price' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'fact_commodity_price' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'scrape_logs' THEN RETURN p_operation IN ('insert', 'retention_delete');
                WHEN 'api_logs' THEN RETURN p_operation IN ('insert', 'retention_delete');
                WHEN 'service_alerts' THEN RETURN p_operation IN ('insert', 'update', 'retention_delete');
                WHEN 'reject_data' THEN RETURN p_operation = 'retention_delete';
                WHEN 'users' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'ai_chat_sessions' THEN RETURN p_operation = 'insert';
                WHEN 'ai_chat_messages' THEN RETURN p_operation = 'insert';
                ELSE RETURN FALSE;
"""

_OPERATION_ALLOWED_049_BRANCHES = _OPERATION_ALLOWED_BRANCHES.replace(
    "WHEN 'service_alerts' THEN RETURN p_operation IN ('insert', 'update', 'retention_delete');",
    "WHEN 'service_alerts' THEN RETURN p_operation IN ('insert', 'retention_delete');",
)

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
    op.execute(_operation_allowed_fn(_OPERATION_ALLOWED_BRANCHES))


def downgrade() -> None:
    op.execute(_operation_allowed_fn(_OPERATION_ALLOWED_049_BRANCHES))
