"""Product pool maintenance helpers (batched deletes for large tables)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

BATCH_SIZE = 10_000


async def clear_product_pool_preserve_marketplaces(db: AsyncSession) -> dict[str, int]:
    """
    Remove listings/products/prices/logs while keeping dim_marketplace rows.

    Uses batched DELETE to avoid statement timeouts on large pools.
    """
    listings_before = int((await db.execute(text("SELECT COUNT(*) FROM fact_listing"))).scalar() or 0)
    products_before = int((await db.execute(text("SELECT COUNT(*) FROM dim_product"))).scalar() or 0)
    prices_before = int((await db.execute(text("SELECT COUNT(*) FROM fact_price"))).scalar() or 0)

    await db.execute(
        text(
            """
            UPDATE alert_events
            SET listing_id = NULL
            WHERE listing_id IS NOT NULL
            """
        )
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
        )
    )
    await db.execute(text("DELETE FROM user_products"))

    while True:
        result = await db.execute(
            text(
                """
                DELETE FROM fact_listing
                WHERE id IN (SELECT id FROM fact_listing LIMIT :limit)
                """
            ),
            {"limit": BATCH_SIZE},
        )
        if result.rowcount == 0:
            break

    while True:
        result = await db.execute(
            text(
                """
                DELETE FROM dim_product
                WHERE id IN (SELECT id FROM dim_product LIMIT :limit)
                """
            ),
            {"limit": BATCH_SIZE},
        )
        if result.rowcount == 0:
            break

    await db.execute(text("TRUNCATE TABLE fact_price RESTART IDENTITY CASCADE"))
    await db.execute(text("TRUNCATE TABLE fact_review, fact_stock, fact_promo, fact_search_trend RESTART IDENTITY CASCADE"))
    await db.execute(text("TRUNCATE TABLE scrape_logs RESTART IDENTITY CASCADE"))
    await db.execute(
        text(
            """
            UPDATE dim_marketplace
            SET products_in_pool = 0,
                last_discovery_products_found = 0
            """
        )
    )
    await db.commit()

    return {
        "deleted_listings": listings_before,
        "deleted_products": products_before,
        "deleted_prices": prices_before,
    }
