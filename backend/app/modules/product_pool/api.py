"""Public API for the global product pool."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.common.deps import CurrentSuperuser, CurrentUser, DbSession
from app.modules.product_pool.schemas import (
    PoolCategorySummary,
    PoolProductsResponse,
    PoolStatsResponse,
)
from app.modules.product_pool.service import ProductPoolService

router = APIRouter(prefix="/pool", tags=["product-pool"])
markets_overview_router = APIRouter(prefix="/markets", tags=["markets"])

OVERVIEW_SORT = ("volatile", "trending", "gainers", "losers", "recent")


@markets_overview_router.get("/overview")
async def get_overview(
    current_user: CurrentUser,
    db: DbSession,
    sort: str = Query("volatile", description="Sort: volatile, trending, gainers, losers, recent"),
    search: str | None = Query(None, min_length=2),
    marketplace_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=500, description="Max items per page"),
    offset: int = Query(0, ge=0),
    display_currency: str = Query("local", description="local|EUR|USD"),
) -> dict:
    """Dashboard overview list. Public path `/markets/overview` is preserved
    verbatim from the dissolved dashboard module; the load-bearing frontend
    consumer is `marketsApi.getOverview` in `MarketsOverviewSection`.
    """
    if sort not in OVERVIEW_SORT:
        sort = "volatile"
    service = ProductPoolService(db)
    items, total = await service.list_products(
        sort=sort,
        search=search,
        marketplace_id=marketplace_id,
        limit=limit,
        offset=offset,
        include_blocked_countries=bool(getattr(current_user, "is_superuser", False)),
        display_currency=display_currency,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}

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
    display_currency: str = Query("local", description="local|EUR|USD"),
):
    service = ProductPoolService(db)
    items, total = await service.list_products(
        sort=sort,
        search=search,
        marketplace_id=marketplace_id,
        category=category,
        limit=limit,
        offset=offset,
        include_blocked_countries=bool(getattr(current_user, "is_superuser", False)),
        display_currency=display_currency,
    )
    return PoolProductsResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/categories")
async def pool_categories(current_user: CurrentUser, db: DbSession) -> list[dict]:
    service = ProductPoolService(db)
    return await service.get_categories(
        include_blocked_countries=bool(getattr(current_user, "is_superuser", False)),
    )


@router.get("/marketplace-stats", response_model=list[PoolCategorySummary])
async def pool_marketplace_stats(current_user: CurrentUser, db: DbSession):
    service = ProductPoolService(db)
    return await service.get_marketplace_stats(
        include_blocked_countries=bool(getattr(current_user, "is_superuser", False)),
    )


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
    service = ProductPoolService(db)
    items = await service.search_products(
        query=q,
        limit=limit,
        include_blocked_countries=bool(getattr(current_user, "is_superuser", False)),
    )
    return {"items": items, "total": len(items)}
