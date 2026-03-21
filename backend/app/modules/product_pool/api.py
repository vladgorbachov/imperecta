"""Public API for the global product pool (v2 migration stub)."""

from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.common.deps import CurrentSuperuser, CurrentUser, DbSession
from app.modules.product_pool.schemas import (
    PoolCategorySummary,
    PoolProductsResponse,
    PoolStatsResponse,
)
from app.modules.product_pool.service import ProductPoolService

router = APIRouter(prefix="/pool", tags=["product-pool"])

_MIG = "Endpoint pending migration to v2 schema"


class PoolBulkDeleteBody(BaseModel):
    product_ids: list[int]


@router.delete("/products/bulk")
async def bulk_delete_pool_products(
    body: PoolBulkDeleteBody,
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    _ = db, body
    return {"deleted": 0, "message": _MIG}


@router.get("/products", response_model=PoolProductsResponse)
async def list_pool_products(
    current_user: CurrentUser,
    db: DbSession,
    search: str | None = Query(None, min_length=2, description="Search by title"),
    marketplace_id: UUID | None = Query(None, description="Filter by marketplace UUID"),
    category: str | None = Query(None, description="Filter by marketplace domain/name"),
    sort: str = Query(
        "recent",
        description="recent|name_asc|name_desc|price_asc|price_desc|trending|gainers|losers|volatile",
    ),
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    _ = current_user
    service = ProductPoolService(db)
    items, total = await service.list_products(
        sort=sort,
        search=search,
        marketplace_id=marketplace_id,
        category=category,
        limit=limit,
        offset=offset,
    )
    return PoolProductsResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/categories")
async def pool_categories(current_user: CurrentUser, db: DbSession) -> list[dict]:
    _ = current_user
    service = ProductPoolService(db)
    return await service.get_categories()


@router.get("/marketplace-stats", response_model=list[PoolCategorySummary])
async def pool_marketplace_stats(current_user: CurrentUser, db: DbSession):
    _ = current_user
    service = ProductPoolService(db)
    return await service.get_marketplace_stats()


@router.get("/stats", response_model=PoolStatsResponse)
async def pool_stats(current_user: CurrentUser, db: DbSession):
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
    _ = current_user
    service = ProductPoolService(db)
    items = await service.search_products(query=q, limit=limit)
    return {"items": items, "total": len(items), "message": _MIG}
