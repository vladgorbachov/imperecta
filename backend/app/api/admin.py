"""Admin API endpoints (superuser only)."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl

from app.services.seed_service import seed_products_for_user
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.models import AdminMarketplace, Competitor, CompetitorProduct, ScrapeLog, User
from app.models.product import Product
from app.services.claude_monitor import check_claude_api_health, get_claude_api_stats

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_superuser)],
)

# Built-in marketplace registry (ozon, wildberries, kaspi)
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


class SeedProductsRequest(BaseModel):
    """Request body for seed-products endpoint."""

    limit: int = 20


@router.post("/seed-products")
async def admin_seed_products(
    db: DbSession,
    current_user: CurrentSuperuser,
    data: SeedProductsRequest | None = Body(default=None),
) -> dict:
    """Seed current superuser account with real products for scraping test."""
    limit = data.limit if data else 20
    return await seed_products_for_user(db, current_user.id, limit=limit)


@router.post("/trigger-scrape")
async def admin_trigger_scrape() -> dict:
    """Manually trigger scraping for all active competitor_products."""
    from app.workers.scrape_tasks import scrape_all

    task = scrape_all.delay()
    return {"message": "Scrape task queued", "task_id": str(task.id)}


class AddMarketplaceRequest(BaseModel):
    """Request body for adding marketplace by URL."""

    url: HttpUrl


@router.post("/marketplaces")
async def admin_add_marketplace(data: AddMarketplaceRequest, db: DbSession) -> dict:
    """Add new marketplace by URL."""
    parsed = urlparse(str(data.url))
    domain = parsed.netloc or parsed.path
    if not domain:
        raise HTTPException(status_code=422, detail="Invalid URL: could not extract domain")
    domain = domain.lower().replace("www.", "").strip("/")
    if not domain:
        raise HTTPException(status_code=422, detail="Invalid URL: could not extract domain")

    marketplace_id = _domain_to_marketplace_id(domain)

    for reg in MARKETPLACE_REGISTRY:
        if reg["marketplace_id"] == marketplace_id:
            raise HTTPException(status_code=409, detail="Marketplace already exists in registry")

    existing = await db.execute(
        select(AdminMarketplace).where(AdminMarketplace.marketplace_id == marketplace_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Marketplace already exists")

    tld = domain.split(".")[-1] if "." in domain else "com"
    country = TLD_TO_COUNTRY.get(tld, "XX")
    region = "cis" if country in ("RU", "KZ", "BY", "UA") else "other"
    base_url = f"https://{domain}"

    am = AdminMarketplace(
        marketplace_id=marketplace_id,
        name=domain,
        domain=domain,
        base_url=base_url,
        country=country,
        region=region,
        currency="USD",
        scraper_type="generic",
        is_active=True,
    )
    db.add(am)
    await db.flush()
    await db.refresh(am)

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
