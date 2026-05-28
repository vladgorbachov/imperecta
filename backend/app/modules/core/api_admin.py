"""Core admin endpoints (non-parsing)."""

from time import perf_counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.config import Settings
from app.models.core import User
from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing
from app.modules.ai_analyst.claude_client import resolve_claude_model

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
    resolved_model: str | None = None
    if settings.claude_api_key:
        try:
            resolved_model = await resolve_claude_model(settings.claude_model, settings.claude_api_key)
        except Exception:
            resolved_model = None
    return {
        "configured": bool(settings.claude_api_key),
        "model": resolved_model or settings.claude_model,
        "model_config": settings.claude_model,
    }


@router.post("/products/clear-pool")
async def clear_pool(_current_user: CurrentSuperuser, db: DbSession) -> dict:
    """Clear product pool data; keeps dim_marketplace and dimension seeds."""
    from app.modules.core.pool_maintenance import clear_product_pool_preserve_marketplaces

    started = perf_counter()
    counts = await clear_product_pool_preserve_marketplaces(db)
    elapsed_ms = int((perf_counter() - started) * 1000)
    return {
        "status": "pool_cleared",
        "deleted_listings": counts["deleted_listings"],
        "deleted_products": counts["deleted_products"],
        "deleted_prices": counts["deleted_prices"],
        "time_ms": elapsed_ms,
    }
