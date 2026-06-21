"""Product pool maintenance — complete blank-slate reset (admin-only)."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.sentry_init import capture_exception_if_initialized
from app.workers.maintenance_tasks import _has_active_scrape_job, _refresh_mv

slog = structlog.get_logger(__name__)

_MATERIALIZED_VIEWS: tuple[str, ...] = (
    "mv_daily_price_summary",
    "mv_marketplace_health",
)

_ANALYZE_TABLES: tuple[str, ...] = (
    "fact_listing",
    "dim_product",
    "fact_price",
    "fact_review",
    "fact_stock",
    "fact_promo",
    "fact_search_trend",
    "scrape_logs",
    "reject_data",
)


class PoolResetBlockedError(RuntimeError):
    """Raised when pool reset is requested while scrape/discovery jobs are active."""


async def _table_count(db: AsyncSession, table: str) -> int:
    """Return row count for a public table (empty / missing table → 0)."""
    result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
    return int(result.scalar() or 0)


async def _run_post_wipe_maintenance(db: AsyncSession) -> tuple[bool, str | None]:
    """Best-effort MV refresh + ANALYZE; must never fail the pool reset contract."""
    try:
        for view_name in _MATERIALIZED_VIEWS:
            _refresh_mv(view_name)
        for table_name in _ANALYZE_TABLES:
            await db.execute(text(f"ANALYZE {table_name}"))
        await db.commit()
        slog.info("reset_mv_refreshed", views=list(_MATERIALIZED_VIEWS))
        return True, None
    except Exception as exc:
        post_error = str(exc)[:2000]
        slog.warning(
            "reset_post_maintenance_failed",
            error=post_error,
            exc_info=True,
        )
        capture_exception_if_initialized(exc)
        try:
            await db.rollback()
        except Exception:
            pass
        return False, post_error


async def clear_product_pool_preserve_marketplaces(db: AsyncSession) -> dict[str, Any]:
    """
    Wipe e-commerce pool data and discovery cursors; preserve marketplaces and seeds.

    Uses TRUNCATE CASCADE for instant reclaim. Market-data facts (forex/crypto/commodity)
    are untouched. Requires an idle scrape pool (no running pipeline/scrape/discovery jobs).
    """
    if _has_active_scrape_job():
        raise PoolResetBlockedError(
            "Cannot reset pool while pipeline, scrape, or discovery jobs are running",
        )

    counts_before = {
        "deleted_listings": await _table_count(db, "fact_listing"),
        "deleted_products": await _table_count(db, "dim_product"),
        "deleted_prices": await _table_count(db, "fact_price"),
        "deleted_scrape_logs": await _table_count(db, "scrape_logs"),
        "deleted_reject_data": await _table_count(db, "reject_data"),
    }
    marketplaces_preserved = await _table_count(db, "dim_marketplace")
    slog.info("reset_pool_started", **counts_before)

    await db.execute(
        text(
            """
            UPDATE alert_events
            SET listing_id = NULL
            WHERE listing_id IS NOT NULL
            """
        ),
    )
    await db.execute(
        text(
            """
            UPDATE alerts
            SET listing_id = NULL,
                product_id = NULL,
                marketplace_id = NULL
            WHERE listing_id IS NOT NULL
               OR product_id IS NOT NULL
               OR marketplace_id IS NOT NULL
            """
        ),
    )
    await db.execute(text("DELETE FROM user_products"))

    await db.execute(text("TRUNCATE TABLE reject_data RESTART IDENTITY CASCADE"))
    slog.info("reset_reject_data_cleared", rows_before=counts_before["deleted_reject_data"])

    await db.execute(text("TRUNCATE TABLE fact_price RESTART IDENTITY CASCADE"))
    await db.execute(
        text(
            "TRUNCATE TABLE fact_review, fact_stock, fact_promo, fact_search_trend "
            "RESTART IDENTITY CASCADE",
        ),
    )
    await db.execute(text("TRUNCATE TABLE scrape_logs RESTART IDENTITY CASCADE"))
    await db.execute(text("TRUNCATE TABLE fact_listing RESTART IDENTITY CASCADE"))
    await db.execute(text("TRUNCATE TABLE dim_product RESTART IDENTITY CASCADE"))
    slog.info("reset_truncated", **counts_before)

    await db.execute(
        text(
            """
            UPDATE dim_marketplace
            SET products_in_pool = 0,
                last_discovery_products_found = 0,
                discovery_error_count = 0,
                sitemap_resume_offset = 0,
                category_resume_index = 0,
                recon_frontier_state = NULL,
                discovered_category_urls = '[]'::jsonb,
                last_sitemap_harvest_at = NULL,
                last_category_recon_at = NULL,
                last_discovery_at = NULL,
                last_discovery_status = NULL
            """
        ),
    )
    slog.info("reset_cursors_cleared")

    await db.commit()

    mv_refreshed, post_maintenance_error = await _run_post_wipe_maintenance(db)

    slog.info("reset_completed", **counts_before)
    return {
        "pool_cleared": True,
        "fact_listing_deleted": counts_before["deleted_listings"],
        "dim_product_deleted": counts_before["deleted_products"],
        "fact_price_deleted": counts_before["deleted_prices"],
        "scrape_logs_deleted": counts_before["deleted_scrape_logs"],
        "reject_data_deleted": counts_before["deleted_reject_data"],
        "marketplaces_preserved": marketplaces_preserved,
        "cursors_reset": True,
        "mv_refreshed": mv_refreshed,
        "post_maintenance_error": post_maintenance_error,
    }
