"""Remove in_stock tracking — drop columns and fact_stock; rebuild daily price MV.

Revision ID: 027_remove_in_stock_and_fact_stock
Revises: 026_forex_nine_currency_allowlist
Create Date: 2026-06-21
"""

from alembic import op

from app.modules.core.supabase_security import harden_materialized_view_statements

revision = "027_remove_in_stock_and_fact_stock"
down_revision = "026_forex_nine_currency_allowlist"
branch_labels = None
depends_on = None

_MV_DAILY_PRICE_SUMMARY = """
CREATE MATERIALIZED VIEW mv_daily_price_summary AS
SELECT
    fp.date_id,
    fl.product_id,
    fl.marketplace_id,
    dp.category_id,
    dp.brand_id,
    dm.country_code,
    COUNT(DISTINCT fl.id) AS listing_count,
    MIN(fp.price_eur) AS min_price_eur,
    MAX(fp.price_eur) AS max_price_eur,
    AVG(fp.price_eur)::NUMERIC(12,2) AS avg_price_eur,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fp.price_eur) AS median_price_eur,
    COUNT(*) FILTER (WHERE fp.is_promoted = true) AS promoted_count,
    AVG(fp.discount_pct) FILTER (WHERE fp.discount_pct > 0) AS avg_discount_pct
FROM fact_price fp
JOIN fact_listing fl ON fp.listing_id = fl.id
JOIN dim_product dp ON fl.product_id = dp.id
JOIN dim_marketplace dm ON fl.marketplace_id = dm.id
GROUP BY fp.date_id, fl.product_id, fl.marketplace_id, dp.category_id, dp.brand_id, dm.country_code
WITH NO DATA;
"""

_MV_DAILY_PRICE_INDEXES = """
CREATE UNIQUE INDEX idx_mv_daily_price ON mv_daily_price_summary
    (date_id, product_id, marketplace_id);
CREATE INDEX idx_mv_daily_price_date ON mv_daily_price_summary (date_id);
CREATE INDEX idx_mv_daily_price_product ON mv_daily_price_summary (product_id);
CREATE INDEX idx_mv_daily_price_category ON mv_daily_price_summary (category_id);
"""


def upgrade() -> None:
    """Drop stock columns/table and rebuild mv_daily_price_summary without stock aggregates."""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_daily_price_summary CASCADE")
    op.execute("ALTER TABLE fact_price DROP COLUMN IF EXISTS in_stock")
    op.execute("ALTER TABLE fact_listing DROP COLUMN IF EXISTS last_in_stock")
    op.execute("ALTER TABLE scrape_logs DROP COLUMN IF EXISTS in_stock_found")
    op.execute(
        """
        DELETE FROM alert_events
        WHERE alert_id IN (
            SELECT id FROM alerts
            WHERE alert_type IN ('out_of_stock', 'back_in_stock')
        )
        """
    )
    op.execute(
        "DELETE FROM alerts WHERE alert_type IN ('out_of_stock', 'back_in_stock')"
    )
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS ck_alerts_alert_type")
    op.execute(
        """
        ALTER TABLE alerts
        ADD CONSTRAINT ck_alerts_alert_type
        CHECK (alert_type IN (
            'price_drop','price_increase','price_threshold',
            'new_competitor','competitor_promo',
            'review_drop','review_spike',
            'trend_spike','trend_drop',
            'currency_shift'
        ))
        """
    )
    op.execute("DROP TABLE IF EXISTS fact_stock CASCADE")
    op.execute(_MV_DAILY_PRICE_SUMMARY)
    op.execute(_MV_DAILY_PRICE_INDEXES)
    for statement in harden_materialized_view_statements("mv_daily_price_summary"):
        op.execute(statement)


def downgrade() -> None:
    """Faithful recreation would require fact_stock DDL, column defaults, and MV stock counts."""
    raise NotImplementedError(
        "027_remove_in_stock_and_fact_stock downgrade is not supported: restoring "
        "fact_stock, fact_price.in_stock, fact_listing.last_in_stock, and "
        "mv_daily_price_summary stock aggregate columns is not warranted for a "
        "deliberate schema removal.",
    )
