"""Admin dashboard endpoints: stats, users, claude-status, clear-test-data, diagnostics."""

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, or_, select, text

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.config import Settings
from app.models import AdminMarketplace, GlobalProduct, User
from app.modules.market_data.models import (
    MarketsCommodity,
    MarketsCrypto,
    MarketsForex,
    MarketsRefreshLog,
)
from app.modules.user_products.models import CompetitorProduct, PriceSnapshot, Product

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_superuser)],
)


@router.get("/stats")
async def admin_stats(_current_user: CurrentSuperuser, db: DbSession) -> dict:
    """Admin dashboard stats."""
    users = await db.scalar(select(func.count()).select_from(User))
    marketplaces = await db.scalar(
        select(func.count())
        .select_from(AdminMarketplace)
        .where(AdminMarketplace.is_active.is_(True))
    )
    products = await db.scalar(select(func.count()).select_from(GlobalProduct))
    return {
        "users": users or 0,
        "marketplaces": marketplaces or 0,
        "products_in_pool": products or 0,
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
            "plan": u.plan.value if u.plan else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        }
        for u in users
    ]


@router.get("/diagnostics/sample-products")
async def sample_products(_current_user: CurrentSuperuser, db: DbSession) -> list[dict]:
    """Show 10 sample global products with full data for debugging."""
    result = await db.execute(
        select(GlobalProduct).order_by(GlobalProduct.id).limit(10)
    )
    products = result.scalars().all()
    return [
        {
            "id": p.id,
            "url": (p.url or "")[:200],
            "url_length": len(p.url or ""),
            "title": p.title,
            "current_price": float(p.current_price) if p.current_price is not None else None,
            "image_url": (p.image_url or "")[:100] if p.image_url else None,
            "status": p.status,
            "marketplace_id": p.marketplace_id,
            "last_scraped_at": p.last_scraped_at.isoformat() if p.last_scraped_at else None,
            "scrape_error_count": p.scrape_error_count,
            "last_scraper_layer": p.last_scraper_layer,
        }
        for p in products
    ]


@router.get("/api-health")
async def api_health_status(_current_user: CurrentSuperuser, db: DbSession) -> dict:
    """Real-time health status of all external API integrations."""
    result = await db.execute(
        select(MarketsRefreshLog)
        .order_by(MarketsRefreshLog.started_at.desc())
        .limit(50)
    )
    logs = result.scalars().all()

    providers: dict[str, dict] = {}
    for log in logs:
        key = log.refresh_type.value if hasattr(log.refresh_type, "value") else str(log.refresh_type)
        if key not in providers:
            providers[key] = {
                "type": key,
                "status": log.status.value if hasattr(log.status, "value") else str(log.status),
                "last_refresh": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                "error": log.error_message,
                "provider": log.provider_source,
            }

    forex_count = await db.scalar(select(func.count()).select_from(MarketsForex))
    crypto_count = await db.scalar(select(func.count()).select_from(MarketsCrypto))
    commodities_count = await db.scalar(select(func.count()).select_from(MarketsCommodity))
    if "forex" in providers:
        providers["forex"]["items_count"] = forex_count or 0
    if "crypto" in providers:
        providers["crypto"]["items_count"] = crypto_count or 0
    if "commodities" in providers:
        providers["commodities"]["items_count"] = commodities_count or 0

    settings = Settings()
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

    return {"providers": providers, "api_keys": api_keys}


@router.get("/claude-status")
async def admin_claude_status(_current_user: CurrentSuperuser) -> dict:
    """Claude API status."""
    settings = Settings()
    return {
        "configured": bool(settings.claude_api_key),
        "model": settings.claude_model,
    }


@router.delete("/products/clear-test-data")
async def clear_test_products(_current_user: CurrentSuperuser, db: DbSession) -> dict:
    """Delete all user products (test CSV data). Superuser only. CASCADE handles related records."""
    count = await db.scalar(select(func.count()).select_from(Product))
    await db.execute(delete(Product))
    await db.commit()
    return {"deleted": count or 0}


@router.post("/products/cleanup-invalid")
async def cleanup_invalid_products(_current_user: CurrentSuperuser, db: DbSession) -> dict:
    """
    Delete global_products with invalid URLs or category page titles.
    Call before re-running discovery after fixing discovery bugs.
    """
    long_result = await db.execute(
        delete(GlobalProduct).where(func.length(GlobalProduct.url) > 2000)
    )
    long_deleted = long_result.rowcount or 0

    invalid_result = await db.execute(
        delete(GlobalProduct).where(~GlobalProduct.url.startswith("http"))
    )
    invalid_deleted = invalid_result.rowcount or 0

    category_result = await db.execute(
        delete(GlobalProduct).where(
            or_(
                GlobalProduct.title.ilike("%каталог%огляди%відгуки%"),
                GlobalProduct.title.ilike("%| купити в інтернет-магазині%"),
                GlobalProduct.title.ilike("% - вигідні ціни | купити%"),
                GlobalProduct.title.ilike("%ціни, відгуки - купити%"),
            )
        )
    )
    category_deleted = category_result.rowcount or 0

    await db.commit()
    return {
        "deleted_long_urls": long_deleted,
        "deleted_invalid_urls": invalid_deleted,
        "deleted_category_pages": category_deleted,
    }


@router.post("/products/clear-pool")
async def clear_pool(_current_user: CurrentSuperuser, db: DbSession) -> dict:
    """Delete ALL global products and snapshots to start fresh. Superuser only."""
    from sqlalchemy import update

    from app.models import GlobalPriceSnapshot

    count = await db.scalar(select(func.count()).select_from(GlobalProduct))
    await db.execute(delete(GlobalPriceSnapshot))
    await db.execute(delete(GlobalProduct))
    await db.execute(update(AdminMarketplace).values(products_in_pool=0))
    await db.commit()
    return {"deleted": count or 0, "message": "Pool cleared. Run discovery again."}


@router.post("/products/clear-user-data")
async def clear_user_products(_current_user: CurrentSuperuser, db: DbSession) -> dict:
    """
    Delete ALL user-created products (from CSV/manual import).
    Does NOT touch global_products pool.
    CASCADE deletes: price_snapshots, competitor_products.
    """
    count_before = await db.scalar(select(func.count()).select_from(Product))
    await db.execute(delete(PriceSnapshot))
    await db.execute(delete(CompetitorProduct))
    await db.execute(delete(Product))
    await db.commit()
    return {"status": "cleared", "deleted_products": count_before or 0}


@router.get("/diagnostics/pool")
async def diagnose_pool(_current_user: CurrentSuperuser, db: DbSession) -> dict:
    """
    Full diagnostic of marketplace pool, global products, discovery status.
    Returns everything needed to understand why data is missing.
    """
    mp_res = await db.execute(text("SELECT COUNT(*) FROM admin_marketplaces"))
    mp_total = mp_res.scalar() or 0
    mp_active_res = await db.execute(
        text("SELECT COUNT(*) FROM admin_marketplaces WHERE is_active = true")
    )
    mp_active = mp_active_res.scalar() or 0

    quota_res = await db.execute(text("""
        SELECT domain, product_quota, COALESCE(products_in_pool, 0) as products_in_pool,
               is_active, requires_js, last_discovery_at
        FROM admin_marketplaces
        WHERE is_active = true
        ORDER BY domain
    """))
    marketplaces = [
        {
            "domain": r[0],
            "quota": r[1],
            "products": r[2],
            "active": r[3],
            "requires_js": r[4],
            "last_discovery": r[5].isoformat() if r[5] else None,
        }
        for r in quota_res.fetchall()
    ]

    zero_quota = sum(1 for m in marketplaces if (m["quota"] or 0) == 0)

    gp_res = await db.execute(text("SELECT COUNT(*) FROM global_products"))
    gp_total = gp_res.scalar() or 0
    gp_status = {}
    status_res = await db.execute(
        text("SELECT status, COUNT(*) FROM global_products GROUP BY status")
    )
    for r in status_res.fetchall():
        gp_status[r[0]] = r[1]

    gs_res = await db.execute(text("SELECT COUNT(*) FROM global_price_snapshots"))
    gs_total = gs_res.scalar() or 0

    dl_res = await db.execute(text("SELECT COUNT(*) FROM discovery_logs"))
    dl_total = dl_res.scalar() or 0
    dl_detail = await db.execute(text("""
        SELECT am.domain, dl.status, dl.products_found, dl.products_new,
               dl.errors_count, dl.error_message, dl.started_at, dl.duration_seconds
        FROM discovery_logs dl
        JOIN admin_marketplaces am ON am.id = dl.marketplace_id
        ORDER BY dl.started_at DESC
        LIMIT 10
    """))
    discovery_logs = [
        {
            "domain": r[0],
            "status": r[1],
            "found": r[2],
            "new": r[3],
            "errors": r[4],
            "error": (r[5][:300] if r[5] else None),
            "started_at": r[6].isoformat() if r[6] else None,
            "duration_s": r[7],
        }
        for r in dl_detail.fetchall()
    ]

    up_res = await db.execute(text("SELECT COUNT(*) FROM products"))
    user_products = up_res.scalar() or 0

    problems = []
    if mp_total > 0 and mp_active == 0:
        problems.append("All marketplaces are inactive (is_active=false)")
    if zero_quota > 0:
        problems.append(
            f"{zero_quota} active marketplaces have zero quota — call POST /admin/marketplaces/recalculate-quotas"
        )
    if gp_total == 0 and dl_total == 0:
        problems.append("Discovery has NEVER run — call POST /admin/discovery/trigger-all")
    if gp_total == 0 and dl_total > 0:
        problems.append("Discovery ran but found 0 products — check discovery_logs errors")
    if gp_total > 0 and gs_total == 0:
        problems.append("Products exist but never scraped — call POST /admin/pool/trigger-scrape")
    if not problems:
        problems.append("No obvious problems detected")

    return {
        "marketplaces": {"total": mp_total, "active": mp_active, "zero_quota": zero_quota},
        "global_products": {"total": gp_total, "by_status": gp_status},
        "price_snapshots": gs_total,
        "discovery_logs": {"total": dl_total, "recent": discovery_logs},
        "user_products": user_products,
        "marketplace_details": marketplaces[:20],
        "diagnosis": problems,
    }
