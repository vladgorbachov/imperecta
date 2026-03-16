"""Public API for the global product pool."""

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.global_product import (
    GlobalProductListResponse,
    PoolCategorySummary,
    PoolStatsResponse,
)
from app.services.product_pool_service import ProductPoolService

router = APIRouter(prefix="/pool", tags=["product-pool"])


@router.get("/products", response_model=GlobalProductListResponse)
async def list_pool_products(
    current_user: CurrentUser,
    db: DbSession,
    sort: str = Query("recent", description="recent|trending|gainers|losers|volatile"),
    search: str | None = Query(None, min_length=2),
    marketplace_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List products from global pool. Used by Market Overview widget."""
    _ = current_user
    service = ProductPoolService(db)
    items, total = await service.list_products(
        sort=sort,
        search=search,
        marketplace_id=marketplace_id,
        limit=limit,
        offset=offset,
    )
    return GlobalProductListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/marketplace-stats", response_model=list[PoolCategorySummary])
async def pool_marketplace_stats(current_user: CurrentUser, db: DbSession):
    """Products grouped by marketplace."""
    _ = current_user
    service = ProductPoolService(db)
    return await service.get_marketplace_stats()


@router.get("/stats", response_model=PoolStatsResponse)
async def pool_stats(current_user: CurrentUser, db: DbSession):
    """Overall pool statistics."""
    _ = current_user
    service = ProductPoolService(db)
    return await service.get_pool_stats()


@router.get("/search")
async def search_pool(
    current_user: CurrentUser,
    db: DbSession,
    q: str = Query(..., min_length=2),
    limit: int = Query(50, ge=1, le=200),
):
    """Search products by title."""
    _ = current_user
    service = ProductPoolService(db)
    items = await service.search_products(query=q, limit=limit)
    return {"items": items, "total": len(items)}
