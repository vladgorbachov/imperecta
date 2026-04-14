"""Admin dashboard endpoints (v2 dim/fact tables)."""

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

_MIGRATION_MSG = "Pending migration to v2 schema"


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


@router.get("/users")
async def admin_users(_current_user: CurrentSuperuser, db: DbSession) -> list[dict]:
    """List all users."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "is_superuser": u.is_superuser,
            "plan": str(u.plan) if u.plan else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        }
        for u in users
    ]


@router.get("/diagnostics/sample-products")
async def sample_products(_current_user: CurrentSuperuser, db: DbSession) -> list[dict]:
    """Sample dim_product rows for debugging."""
    result = await db.execute(select(DimProduct).order_by(DimProduct.id).limit(10))
    rows = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "name_normalized": p.name_normalized[:200] if p.name_normalized else None,
            "sku_universal": p.sku_universal,
            "category_id": str(p.category_id) if p.category_id else None,
        }
        for p in rows
    ]


@router.get("/api-health")
async def api_health_status(_current_user: CurrentSuperuser) -> dict:
    """Static API key / integration hints (market data refresh logs pending v2)."""
    settings = Settings()
    providers: dict[str, dict] = {}
    api_keys = {
        "goldapi": {"configured": bool(settings.goldapi_key), "name": "GoldAPI (Metals)"},
        "alpha_vantage": {"configured": bool(settings.alpha_vantage_key), "name": "Alpha Vantage (Energy)"},
        "coingecko": {"configured": True, "name": "CoinGecko (Crypto backup)"},
        "binance": {"configured": True, "name": "Binance (Crypto primary)"},
        "frankfurter": {"configured": True, "name": "Frankfurter (Forex)"},
        "decodo": {
            "configured": bool(settings.decodo_username and settings.decodo_password),
            "name": "Decodo (Web Scraping)",
        },
        "claude": {"configured": bool(settings.claude_api_key), "name": "Claude AI"},
        "resend": {"configured": bool(settings.resend_api_key), "name": "Resend (Email)"},
        "telegram": {"configured": bool(settings.telegram_bot_token), "name": "Telegram Bot"},
    }
    return {"providers": providers, "api_keys": api_keys, "message": _MIGRATION_MSG}


@router.get("/claude-status")
async def admin_claude_status(_current_user: CurrentSuperuser) -> dict:
    """Claude API status."""
    settings = Settings()
    return {
        "configured": bool(settings.claude_api_key),
        "model": settings.claude_model,
    }


@router.post("/products/cleanup-invalid")
async def cleanup_invalid_products(_current_user: CurrentSuperuser, db: DbSession) -> dict:
    """Remove pool listings with NULL or non-http(s) URLs."""
    res = await db.execute(
        text(
            """
            DELETE FROM fact_listing
            WHERE external_url IS NULL
               OR btrim(external_url) = ''
               OR external_url NOT ILIKE 'http%'
            """
        ),
    )
    await db.commit()
    deleted = res.rowcount or 0
    return {
        "deleted_long_urls": 0,
        "deleted_invalid_urls": int(deleted),
        "deleted_category_pages": 0,
        "message": None,
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


@router.post("/products/clear-user-data")
async def clear_user_products(_current_user: CurrentSuperuser) -> dict:
    """Placeholder."""
    return {"status": "skipped", "deleted_products": 0, "message": _MIGRATION_MSG}


@router.get("/diagnostics/pool")
async def diagnose_pool(_current_user: CurrentSuperuser, db: DbSession) -> dict:
    """High-level counts from v2 dim/fact tables (raw SQL for diagnostics)."""
    mp_total = (await db.execute(text("SELECT COUNT(*) FROM dim_marketplace"))).scalar()
    mp_active = (
        await db.execute(text("SELECT COUNT(*) FROM dim_marketplace WHERE is_active = true"))
    ).scalar()
    listing_total = (await db.execute(text("SELECT COUNT(*) FROM fact_listing"))).scalar()
    listing_active = (
        await db.execute(text("SELECT COUNT(*) FROM fact_listing WHERE is_active = true"))
    ).scalar()
    price_total = (await db.execute(text("SELECT COUNT(*) FROM fact_price"))).scalar()
    discovery_total = (
        await db.execute(text("SELECT COUNT(*) FROM scrape_jobs WHERE job_type = 'discovery'"))
    ).scalar()
    dim_product_total = (await db.execute(text("SELECT COUNT(*) FROM dim_product"))).scalar()
    user_product_total = (await db.execute(text("SELECT COUNT(*) FROM user_products"))).scalar()

    return {
        "marketplaces": {
            "total": int(mp_total or 0),
            "active": int(mp_active or 0),
            "zero_quota": 0,
        },
        "global_products": {"total": int(dim_product_total or 0), "by_status": {}},
        "price_snapshots": int(price_total or 0),
        "listings": {"total": int(listing_total or 0), "active": int(listing_active or 0)},
        "discovery_logs": {"total": int(discovery_total or 0), "recent": []},
        "user_products": int(user_product_total or 0),
        "marketplace_details": [],
        "diagnosis": [],
    }
