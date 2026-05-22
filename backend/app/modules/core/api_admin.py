"""Core admin endpoints (non-parsing)."""

from time import perf_counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.config import Settings
from app.models.core import User
from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_superuser)],
)

@router.get("/stats")
async def admin_stats(_current_user: CurrentSuperuser, db: DbSession) -> dict:
    """Admin dashboard stats (v2 ORM counts)."""
    users = await db.scalar(select(func.count()).select_from(User))
    marketplaces = await db.scalar(
        select(func.count()).select_from(DimMarketplace).where(DimMarketplace.is_active.is_(True)),
    )
    products = await db.scalar(select(func.count()).select_from(DimProduct))
    listings = await db.scalar(select(func.count()).select_from(FactListing))
    u = users or 0
    m = marketplaces or 0
    return {
        "users": u,
        "marketplaces": m,
        "products": products or 0,
        "listings": listings or 0,
        "users_count": u,
        "marketplaces_count": m,
    }


@router.get("/claude-status")
async def admin_claude_status(_current_user: CurrentSuperuser) -> dict:
    """Claude API status."""
    settings = Settings()
    return {
        "configured": bool(settings.claude_api_key),
        "model": settings.claude_model,
    }


@router.post("/products/clear-pool")
async def clear_pool(_current_user: CurrentSuperuser, db: DbSession) -> dict:
    """Hard-clear marketplace/product pool data while preserving system dimensions/users."""
    started = perf_counter()
    deleted_marketplaces = int(
        (await db.execute(text("SELECT COUNT(*) FROM dim_marketplace"))).scalar() or 0,
    )
    deleted_listings = int(
        (await db.execute(text("SELECT COUNT(*) FROM fact_listing"))).scalar() or 0,
    )
    deleted_prices = int(
        (await db.execute(text("SELECT COUNT(*) FROM fact_price"))).scalar() or 0,
    )

    # Keep system tables untouched by nullifying references from retained entities.
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

    # user_products is product-linked business data and should be cleared with the pool.
    await db.execute(text("DELETE FROM user_products"))
    await db.execute(text("UPDATE dim_marketplace SET products_in_pool = 0"))

    await db.execute(
        text(
            """
            TRUNCATE TABLE
                fact_price,
                fact_review,
                fact_stock,
                fact_promo,
                fact_listing,
                scrape_logs,
                scrape_jobs,
                dim_product,
                dim_marketplace
            RESTART IDENTITY
            """
        ),
    )
    await db.commit()
    elapsed_ms = int((perf_counter() - started) * 1000)
    return {
        "status": "pool_cleared",
        "deleted_marketplaces": deleted_marketplaces,
        "deleted_listings": deleted_listings,
        "deleted_prices": deleted_prices,
        "time_ms": elapsed_ms,
    }
