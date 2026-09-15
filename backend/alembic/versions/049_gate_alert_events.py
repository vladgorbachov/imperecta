"""Gate path for public.alert_events + alert_type constraint alignment.

Revision ID: 049_gate_alert_events
Revises: 048_gate_alerts_table
Create Date: 2026-09-15

Two things for the alert trigger engine:

1. Adds `alert_events` to the DB-side gate whitelists: append-only firing
   log (locator ARRAY[]::text[], operation insert — same class as
   scrape_logs). Function bodies mirror 048 verbatim plus the new branches.
2. Aligns ck_alerts_alert_type with the API/door contract: the door and the
   UI use 'price_rise' and 'availability', which the 027 constraint did not
   include — a rule_create with either would have passed the door and died
   on the CHECK. Old values stay valid (existing rows untouched).
"""

from __future__ import annotations

from alembic import op

revision = "049_gate_alert_events"
down_revision = "048_gate_alerts_table"
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
                WHEN 'service_alerts' THEN RETURN p_operation IN ('insert', 'retention_delete');
                WHEN 'reject_data' THEN RETURN p_operation = 'retention_delete';
                WHEN 'users' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'ai_chat_sessions' THEN RETURN p_operation = 'insert';
                WHEN 'ai_chat_messages' THEN RETURN p_operation = 'insert';
                ELSE RETURN FALSE;
"""

_LOCATOR_KEYS_048_BRANCHES = _LOCATOR_KEYS_BRANCHES.replace(
    "                WHEN 'alert_events' THEN RETURN ARRAY[]::text[];\n", ""
)
_OPERATION_ALLOWED_048_BRANCHES = _OPERATION_ALLOWED_BRANCHES.replace(
    "                WHEN 'alert_events' THEN RETURN p_operation = 'insert';\n", ""
)

_ALERT_TYPES_NEW = (
    "'price_drop','price_rise','availability',"
    "'price_increase','price_threshold',"
    "'new_competitor','competitor_promo',"
    "'review_drop','review_spike',"
    "'trend_spike','trend_drop',"
    "'currency_shift'"
)
_ALERT_TYPES_027 = (
    "'price_drop','price_increase','price_threshold',"
    "'new_competitor','competitor_promo',"
    "'review_drop','review_spike',"
    "'trend_spike','trend_drop',"
    "'currency_shift'"
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


def _alert_type_constraint(values: str) -> str:
    return f"""
        ALTER TABLE alerts
        ADD CONSTRAINT ck_alerts_alert_type
        CHECK (alert_type IN ({values}))
    """


def upgrade() -> None:
    op.execute(_locator_keys_fn(_LOCATOR_KEYS_BRANCHES))
    op.execute(_operation_allowed_fn(_OPERATION_ALLOWED_BRANCHES))
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS ck_alerts_alert_type")
    op.execute(_alert_type_constraint(_ALERT_TYPES_NEW))


def downgrade() -> None:
    op.execute(_locator_keys_fn(_LOCATOR_KEYS_048_BRANCHES))
    op.execute(_operation_allowed_fn(_OPERATION_ALLOWED_048_BRANCHES))
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS ck_alerts_alert_type")
    op.execute(_alert_type_constraint(_ALERT_TYPES_027))
