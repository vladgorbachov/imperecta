"""Admin dashboard endpoints (v2 dim/fact tables)."""

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select, text, update

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.config import Settings
from app.models.core import User
from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing, FactPrice

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


@router.delete("/products/clear-test-data")
async def clear_test_products(_current_user: CurrentSuperuser) -> dict:
    """Placeholder until user product import is reimplemented for v2."""
    return {"deleted": 0, "message": _MIGRATION_MSG}


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
    """Delete all pool prices and listings; reset marketplace pool counters."""
    count = await db.scalar(select(func.count()).select_from(FactListing)) or 0
    await db.execute(delete(FactPrice))
    await db.execute(delete(FactListing))
    await db.execute(update(DimMarketplace).values(products_in_pool=0))
    await db.commit()
    return {"deleted_listings": int(count), "message": None}


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
