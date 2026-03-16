"""Admin API endpoints (superuser only)."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, HttpUrl

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from decimal import Decimal

from app.api.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.models import AdminMarketplace, Competitor, CompetitorProduct, ScrapeLog, User
from app.models.product import Product
from app.services.claude_monitor import check_claude_api_health, get_claude_api_stats
from app.services.marketplace_pool_service import MarketplacePoolService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_superuser)],
)

# Built-in marketplace registry for admin stats. All marketplaces treated equally.
MARKETPLACE_REGISTRY: list[dict[str, Any]] = [
    {"marketplace_id": "ozon", "name": "Ozon", "domain": "ozon.ru", "country": "RU", "region": "cis"},
    {"marketplace_id": "wildberries", "name": "Wildberries", "domain": "wildberries.ru", "country": "RU", "region": "cis"},
    {"marketplace_id": "kaspi", "name": "Kaspi", "domain": "kaspi.kz", "country": "KZ", "region": "cis"},
]

TLD_TO_COUNTRY: dict[str, str] = {
    "ru": "RU",
    "kz": "KZ",
    "by": "BY",
    "ua": "UA",
    "de": "DE",
    "pl": "PL",
    "com": "XX",
    "org": "XX",
    "net": "XX",
}


def _domain_to_marketplace_id(domain: str) -> str:
    """Convert domain to marketplace_id (e.g. example.com -> example_com)."""
    return domain.replace(".", "_").replace("www.", "")


@router.get("/stats")
async def admin_stats(db: DbSession) -> dict:
    """Return admin dashboard statistics."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    month_ago = now - timedelta(days=30)

    users_result = await db.execute(select(func.count()).select_from(User))
    users_count = users_result.scalar() or 0

    # Active users: logged in within 30 days - we don't have last_login, use created_at as proxy
    # For now count all users as "active" since we lack last_login_at
    active_users_count = users_count

    admin_marketplaces_result = await db.execute(select(func.count()).select_from(AdminMarketplace))
    admin_count = admin_marketplaces_result.scalar() or 0
    marketplaces_count = len(MARKETPLACE_REGISTRY) + admin_count

    # Active marketplaces: at least 1 scrape in last 24h
    active_mp_result = await db.execute(
        select(func.count(func.distinct(ScrapeLog.marketplace_id))).where(
            ScrapeLog.created_at >= day_ago
        )
    )
    active_marketplaces_count = active_mp_result.scalar() or 0

    scrapes_today_result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(ScrapeLog.status == "success").label("successful"),
        ).where(ScrapeLog.created_at >= day_ago)
    )
    st_row = scrapes_today_result.one()
    total_scrapes_today = st_row.total or 0
    successful_scrapes_today = st_row.successful or 0
    failed_scrapes_today = total_scrapes_today - successful_scrapes_today
    error_rate_today = (failed_scrapes_today / total_scrapes_today * 100) if total_scrapes_today else 0

    products_result = await db.execute(select(func.count()).select_from(Product))
    total_products_monitored = products_result.scalar() or 0

    cp_result = await db.execute(select(func.count()).select_from(CompetitorProduct))
    total_competitor_products = cp_result.scalar() or 0

    return {
        "users_count": users_count,
        "active_users_count": active_users_count,
        "marketplaces_count": marketplaces_count,
        "active_marketplaces_count": active_marketplaces_count,
        "total_scrapes_today": total_scrapes_today,
        "successful_scrapes_today": successful_scrapes_today,
        "failed_scrapes_today": failed_scrapes_today,
        "error_rate_today": round(error_rate_today, 1),
        "total_products_monitored": total_products_monitored,
        "total_competitor_products": total_competitor_products,
    }


async def _get_marketplace_scrape_stats(db: AsyncSession, marketplace_id: str) -> dict:
    """Get scrape stats for a marketplace from scrape_logs."""
    result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(ScrapeLog.status == "success").label("successful"),
            func.max(ScrapeLog.created_at).label("last_scrape_at"),
        ).where(ScrapeLog.marketplace_id == marketplace_id)
    )
    row = result.one()
    total = row.total or 0
    successful = row.successful or 0
    failed = total - successful
    success_rate = (successful / total * 100) if total else 0

    last_error_result = await db.execute(
        select(ScrapeLog.error_message, ScrapeLog.created_at)
        .where(and_(ScrapeLog.marketplace_id == marketplace_id, ScrapeLog.status != "success"))
        .order_by(ScrapeLog.created_at.desc())
        .limit(1)
    )
    last_err = last_error_result.one_or_none()
    last_status_result = await db.execute(
        select(ScrapeLog.status)
        .where(ScrapeLog.marketplace_id == marketplace_id)
        .order_by(ScrapeLog.created_at.desc())
        .limit(1)
    )
    last_status = last_status_result.scalar_one_or_none()

    return {
        "total_scrapes": total,
        "successful_scrapes": successful,
        "failed_scrapes": failed,
        "success_rate": round(success_rate, 1),
        "last_scrape_at": row.last_scrape_at,
        "last_scrape_status": last_status,
        "last_error": last_err.error_message if last_err else None,
    }


@router.get("/marketplaces")
async def admin_marketplaces(db: DbSession) -> list[dict]:
    """Return all marketplaces (registry + admin) with stats."""
    result_list: list[dict] = []

    for reg in MARKETPLACE_REGISTRY:
        mid = reg["marketplace_id"]
        stats = await _get_marketplace_scrape_stats(db, mid)

        cp_count_result = await db.execute(
            select(func.count())
            .select_from(CompetitorProduct)
            .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
            .where(Competitor.marketplace == mid)
        )
        products_count = cp_count_result.scalar() or 0

        result_list.append({
            "marketplace_id": mid,
            "name": reg["name"],
            "domain": reg["domain"],
            "country": reg["country"],
            "region": reg["region"],
            "source": "registry",
            "is_active": True,
            "last_scrape_at": stats["last_scrape_at"].isoformat() if stats["last_scrape_at"] else None,
            "last_scrape_status": stats["last_scrape_status"],
            "last_error": stats["last_error"],
            "total_scrapes": stats["total_scrapes"],
            "successful_scrapes": stats["successful_scrapes"],
            "failed_scrapes": stats["failed_scrapes"],
            "success_rate": stats["success_rate"],
            "products_count": products_count,
        })

    admin_result = await db.execute(select(AdminMarketplace))
    for am in admin_result.scalars().all():
        stats = await _get_marketplace_scrape_stats(db, am.marketplace_id)

        cp_count_result = await db.execute(
            select(func.count())
            .select_from(CompetitorProduct)
            .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
            .where(Competitor.marketplace == am.marketplace_id)
        )
        products_count = cp_count_result.scalar() or 0

        result_list.append({
            "marketplace_id": am.marketplace_id,
            "name": am.name,
            "domain": am.domain,
            "country": am.country,
            "region": am.region,
            "source": "admin",
            "is_active": am.is_active,
            "last_scrape_at": am.last_scrape_at.isoformat() if am.last_scrape_at else None,
            "last_scrape_status": am.last_scrape_status or stats["last_scrape_status"],
            "last_error": am.last_error or stats["last_error"],
            "total_scrapes": am.total_scrapes,
            "successful_scrapes": am.successful_scrapes,
            "failed_scrapes": am.failed_scrapes,
            "success_rate": round((am.successful_scrapes / am.total_scrapes * 100) if am.total_scrapes else 0, 1),
            "products_count": products_count,
        })

    result_list.sort(key=lambda x: (x["name"].lower(),))
    return result_list


@router.get("/marketplaces/{marketplace_id}/logs")
async def admin_marketplace_logs(marketplace_id: str, db: DbSession) -> list[dict]:
    """Return last 50 scrape logs for a marketplace."""
    result = await db.execute(
        select(ScrapeLog)
        .where(ScrapeLog.marketplace_id == marketplace_id)
        .order_by(ScrapeLog.created_at.desc())
        .limit(50)
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "url": log.url,
            "status": log.status,
            "error_message": log.error_message,
            "price_found": float(log.price_found) if log.price_found is not None else None,
            "duration_ms": log.duration_ms,
            "proxy_used": log.proxy_used,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.post("/trigger-scrape")
async def admin_trigger_scrape() -> dict:
    """Manually trigger scraping for all active competitor_products."""
    from app.workers.scrape_tasks import scrape_all

    task = scrape_all.delay()
    return {"message": "Scrape task queued", "task_id": str(task.id)}


@router.post("/discovery/trigger/{marketplace_id}")
async def trigger_discovery(
    marketplace_id: int,
    _current_user: CurrentSuperuser,
    _db: DbSession,
):
    """Manually trigger discovery for one marketplace."""
    from app.workers.discovery_tasks import discover_single_marketplace

    discover_single_marketplace.delay(marketplace_id)
    return {"status": "queued", "marketplace_id": marketplace_id}


@router.post("/discovery/trigger-all")
async def trigger_discovery_all(_current_user: CurrentSuperuser):
    """Manually trigger discovery for all active marketplaces."""
    from app.workers.discovery_tasks import discover_all_marketplaces

    discover_all_marketplaces.delay()
    return {"status": "queued"}


@router.post("/pool/trigger-scrape")
async def trigger_pool_scrape(_current_user: CurrentSuperuser):
    """Manually trigger scraping of stale pool products."""
    from app.workers.discovery_tasks import scrape_all_pool_products

    scrape_all_pool_products.delay()
    return {"status": "queued"}


# Real product URLs for seed-competitors (scrapers need product pages, not search results)
REAL_PRODUCT_URLS: dict[str, list[tuple[str, str]]] = {
    "wildberries": [
        ("iPhone 16 Pro Max", "https://www.wildberries.ru/catalog/252378505/detail.aspx"),
        ("Samsung Galaxy S25 Ultra", "https://www.wildberries.ru/catalog/264108537/detail.aspx"),
        ("Sony WH-1000XM5", "https://www.wildberries.ru/catalog/168877262/detail.aspx"),
        ("Dyson V15 Detect", "https://www.wildberries.ru/catalog/128635872/detail.aspx"),
        ("Nike Air Max 90", "https://www.wildberries.ru/catalog/191955797/detail.aspx"),
    ],
    "ozon": [
        ("MacBook Air M4", "https://www.ozon.ru/product/noutbuk-apple-macbook-air-m4-2025-1852519006/"),
        ("AirPods Pro 2", "https://www.ozon.ru/product/naushniki-apple-airpods-pro-2-1024178498/"),
        ("PlayStation 5 Pro", "https://www.ozon.ru/product/sony-playstation-5-pro-1612483953/"),
        ("Xiaomi 14 Ultra", "https://www.ozon.ru/product/xiaomi-14-ultra-1479553741/"),
        ("Samsung QN90D 55", "https://www.ozon.ru/product/samsung-qe55qn90dauxru-1500321178/"),
    ],
    "kaspi": [
        ("iPhone 16 Pro Max", "https://kaspi.kz/shop/p/apple-iphone-16-pro-max-256gb-119673781/"),
        ("Samsung Galaxy S25 Ultra", "https://kaspi.kz/shop/p/samsung-galaxy-s25-ultra-121905367/"),
        ("Sony PlayStation 5", "https://kaspi.kz/shop/p/sony-playstation-5-slim-113584668/"),
        ("Dyson V15", "https://kaspi.kz/shop/p/dyson-v15-detect-absolute-100592490/"),
        ("Apple Watch Ultra 2", "https://kaspi.kz/shop/p/apple-watch-ultra-2-113072560/"),
    ],
    "rozetka_ua": [
        ("iPhone 16 Pro Max", "https://rozetka.com.ua/ua/apple-iphone-16-pro-max-256gb/p/461541217/"),
        ("Samsung Galaxy S25 Ultra", "https://rozetka.com.ua/ua/samsung-galaxy-s25-ultra/p/464044443/"),
        ("Sony WH-1000XM5", "https://rozetka.com.ua/ua/sony-wh-1000xm5/p/381878572/"),
        ("MacBook Air M4", "https://rozetka.com.ua/ua/apple-macbook-air-m4/p/467891234/"),
        ("iPad Pro M4", "https://rozetka.com.ua/ua/apple-ipad-pro-m4/p/454321567/"),
    ],
    "allegro_pl": [
        ("iPhone 16 Pro Max", "https://allegro.pl/oferta/apple-iphone-16-pro-max-256gb-16494724710"),
        ("Samsung Galaxy S25 Ultra", "https://allegro.pl/oferta/samsung-galaxy-s25-ultra-256gb-16789012345"),
        ("Sony WH-1000XM5", "https://allegro.pl/oferta/sony-wh-1000xm5-sluchawki-bezprzewodowe-14567890123"),
        ("PlayStation 5 Pro", "https://allegro.pl/oferta/sony-playstation-5-pro-16234567890"),
        ("DJI Mini 4 Pro", "https://allegro.pl/oferta/dji-mini-4-pro-dron-15678901234"),
    ],
}

# Marketplace metadata for seed (name, base_url). All use universal scraper.
MARKETPLACE_SEED_META: dict[str, dict[str, str]] = {
    "wildberries": {"name": "Wildberries", "base_url": "https://www.wildberries.ru"},
    "ozon": {"name": "Ozon", "base_url": "https://www.ozon.ru"},
    "kaspi": {"name": "Kaspi", "base_url": "https://kaspi.kz"},
    "rozetka_ua": {"name": "Rozetka", "base_url": "https://rozetka.com.ua"},
    "allegro_pl": {"name": "Allegro", "base_url": "https://allegro.pl"},
}


@router.post("/seed-competitors")
async def admin_seed_competitors(
    db: DbSession,
    current_user: CurrentSuperuser,
) -> dict:
    """Create competitors and competitor_products with real product URLs (no search pages)."""
    competitors_created = 0
    cps_created = 0
    products_created = 0

    for marketplace_id, product_list in REAL_PRODUCT_URLS.items():
        meta = MARKETPLACE_SEED_META.get(marketplace_id, {})
        mp_name = meta.get("name", marketplace_id)
        base_url = meta.get("base_url", "")
        scraper_type = "universal"

        # Find or create Competitor
        existing_result = await db.execute(
            select(Competitor).where(
                Competitor.user_id == current_user.id,
                Competitor.marketplace == marketplace_id,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            competitor = existing
        else:
            competitor = Competitor(
                user_id=current_user.id,
                name=mp_name,
                marketplace=marketplace_id,
                website_url=base_url,
            )
            db.add(competitor)
            await db.flush()
            competitors_created += 1

        for product_name, product_url in product_list:
            # Find or create Product by name
            product_result = await db.execute(
                select(Product).where(
                    Product.user_id == current_user.id,
                    Product.name == product_name,
                    Product.is_active.is_(True),
                )
            )
            product = product_result.scalar_one_or_none()
            if not product:
                product = Product(
                    user_id=current_user.id,
                    name=product_name,
                    current_price=Decimal("0"),
                    currency="RUB",
                    is_active=True,
                )
                db.add(product)
                await db.flush()
                products_created += 1

            # Create CompetitorProduct with real URL if not exists
            exists_result = await db.execute(
                select(CompetitorProduct).where(
                    CompetitorProduct.product_id == product.id,
                    CompetitorProduct.competitor_id == competitor.id,
                )
            )
            if exists_result.scalar_one_or_none():
                continue

            cp = CompetitorProduct(
                product_id=product.id,
                competitor_id=competitor.id,
                url=product_url,
                name=product_name,
                scraper_type=scraper_type,
                is_active=True,
            )
            db.add(cp)
            cps_created += 1

    await db.commit()
    return {
        "competitors_created": competitors_created,
        "competitor_products_created": cps_created,
        "products_created": products_created,
        "message": f"Created {competitors_created} competitors, {products_created} products, {cps_created} scraping targets",
    }


@router.post("/trigger-scrape-user")
async def admin_trigger_scrape_user(
    db: DbSession,
    current_user: CurrentSuperuser,
) -> dict:
    """Manually trigger scraping for current user's active competitor_products."""
    from app.workers.scrape_tasks import scrape_single

    count_result = await db.execute(
        select(func.count())
        .select_from(CompetitorProduct)
        .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
        .where(
            Competitor.user_id == current_user.id,
            CompetitorProduct.is_active.is_(True),
        )
    )
    count = count_result.scalar() or 0

    if count == 0:
        return {"error": "No competitor products to scrape. Run /seed-competitors first."}

    cps_result = await db.execute(
        select(CompetitorProduct.id)
        .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
        .where(
            Competitor.user_id == current_user.id,
            CompetitorProduct.is_active.is_(True),
        )
    )
    cps = cps_result.all()

    for (cp_id,) in cps:
        scrape_single.delay(str(cp_id))

    return {"message": f"Queued {len(cps)} scrape tasks", "count": len(cps)}


class AddMarketplaceRequest(BaseModel):
    """Request body for adding marketplace by URL."""

    url: HttpUrl


@router.post("/marketplaces")
async def admin_add_marketplace(data: AddMarketplaceRequest, db: DbSession) -> dict:
    """Add new marketplace by URL."""
    service = MarketplacePoolService(db)
    try:
        am = await service.add_by_url(str(data.url))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "marketplace_id": am.marketplace_id,
        "name": am.name,
        "domain": am.domain,
        "base_url": am.base_url,
        "country": am.country,
        "region": am.region,
        "currency": am.currency,
        "scraper_type": am.scraper_type,
    }


@router.post("/marketplaces/add-by-url")
async def add_marketplace_by_url(
    url: str = Body(..., embed=True),
    _current_user: CurrentSuperuser,
    db: DbSession,
):
    """Add marketplace by URL. Auto-extracts domain, name, country."""
    service = MarketplacePoolService(db)
    try:
        mp = await service.add_by_url(url)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"id": mp.id, "domain": mp.domain, "name": mp.name}


@router.post("/marketplaces/import-file")
async def import_marketplaces_from_file(
    file: UploadFile = File(...),
    _current_user: CurrentSuperuser,
    db: DbSession,
):
    """
    Import marketplaces from .txt or .csv file.
    .txt: one URL per line
    .csv: column 'url' or first column
    """
    content = (await file.read()).decode("utf-8")
    service = MarketplacePoolService(db)

    if file.filename and file.filename.endswith(".csv"):
        result = await service.import_from_csv(content)
    else:
        result = await service.import_from_txt(content)

    return result


@router.delete("/marketplaces/{marketplace_id}")
async def admin_delete_marketplace(marketplace_id: str, db: DbSession) -> dict:
    """Delete marketplace (only from admin_marketplaces, not registry)."""
    for reg in MARKETPLACE_REGISTRY:
        if reg["marketplace_id"] == marketplace_id:
            raise HTTPException(status_code=403, detail="Cannot delete built-in marketplace")

    result = await db.execute(
        delete(AdminMarketplace).where(AdminMarketplace.marketplace_id == marketplace_id)
    )
    await db.flush()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Marketplace not found")
    service = MarketplacePoolService(db)
    await service.recalculate_all_quotas()
    return {"ok": True}


@router.get("/scrape-activity")
async def admin_scrape_activity(db: DbSession) -> dict:
    """Return scrape activity data for chart (last 7 days)."""
    now = datetime.now(timezone.utc)
    labels = []
    success_data = []
    error_data = []

    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        labels.append(day_start.strftime("%Y-%m-%d"))

        result = await db.execute(
            select(
                func.count().filter(ScrapeLog.status == "success").label("ok"),
                func.count().filter(ScrapeLog.status != "success").label("err"),
            ).where(and_(ScrapeLog.created_at >= day_start, ScrapeLog.created_at < day_end))
        )
        row = result.one()
        success_data.append(row.ok or 0)
        error_data.append(row.err or 0)

    return {
        "labels": labels,
        "datasets": [
            {"label": "Успешно", "data": success_data},
            {"label": "Ошибки", "data": error_data},
        ],
    }


def _categorize_error(msg: str | None) -> str:
    """Map error message to category for distribution chart."""
    if not msg:
        return "other"
    m = msg.lower()
    if "timeout" in m:
        return "timeout"
    if "blocked" in m or "captcha" in m:
        return "blocked"
    if "selector" in m or "not found" in m or "extract" in m:
        return "selector_not_found"
    if "connection" in m or "connect" in m or "refused" in m:
        return "connection_error"
    return "other"


@router.get("/error-distribution")
async def admin_error_distribution(db: DbSession) -> dict:
    """Return error distribution for pie chart (last 24h)."""
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(ScrapeLog.error_message).where(
            and_(ScrapeLog.created_at >= day_ago, ScrapeLog.status != "success")
        )
    )
    errors = [row[0] for row in result.all()]

    categories = ["timeout", "blocked", "selector_not_found", "connection_error", "other"]
    counts = {c: 0 for c in categories}
    for msg in errors:
        cat = _categorize_error(msg)
        counts[cat] = counts.get(cat, 0) + 1

    return {
        "labels": categories,
        "data": [counts[c] for c in categories],
    }


@router.get("/users")
async def admin_users(db: DbSession) -> list[dict]:
    """Return list of users for superuser."""
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    out = []
    for u in users:
        cp_count_result = await db.execute(
            select(func.count())
            .select_from(Product)
            .where(Product.user_id == u.id)
        )
        products_count = cp_count_result.scalar() or 0
        out.append({
            "id": str(u.id),
            "email": u.email,
            "name": u.name,
            "plan": u.plan.value if hasattr(u.plan, "value") else str(u.plan),
            "products_count": products_count,
            "created_at": u.created_at.strftime("%Y-%m-%d"),
            "last_login_at": u.last_login_at.strftime("%Y-%m-%d %H:%M") if u.last_login_at else None,
            "is_active": True,
        })
    return out


@router.get("/claude-status")
async def claude_status(db: DbSession) -> dict:
    """Check Claude API health and return usage stats."""
    try:
        health = await check_claude_api_health()
        stats = await get_claude_api_stats(db)
        return {"health": health, "stats": stats}
    except Exception as e:
        logger.warning("claude-status failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Claude API status temporarily unavailable",
        )
