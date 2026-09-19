"""API for the global product pool — logged-in users only (WP2).

Counsel §2.2/§3.8: the pool is served in bounded pages to authenticated
users; nothing is anonymous, nothing is cached at the edge, nothing is
exported. Every route: `CurrentUser` + the per-user hourly budget
(`app.common.rate_limit`); page size and depth are capped in the query
schema; unfiltered browsing goes through the per-source cap in the
service.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.common.deps import CurrentUser, DbSession
from app.common.rate_limit import user_rate_limit
from app.config import Settings
from app.modules.product_pool.schemas import (
    PoolCategoryItem,
    PoolCategorySummary,
    PoolProductDetail,
    PoolProductsResponse,
    PoolStatsResponse,
    PriceHistoryResponse,
)
from app.modules.product_pool.service import ProductPoolService

_settings = Settings()
PAGE_SIZE_MAX = _settings.pool_page_size_max
OFFSET_MAX = _settings.pool_page_size_max * (_settings.pool_page_depth_max - 1)
PoolBudget = Annotated[
    None, Depends(user_rate_limit("pool", lambda: Settings().pool_rate_limit_per_hour))
]

router = APIRouter(prefix="/pool", tags=["product-pool"])


@router.get("/products", response_model=PoolProductsResponse)
async def list_pool_products(
    current_user: CurrentUser,
    db: DbSession,
    _budget: PoolBudget,
    search: str | None = Query(None, min_length=2, description="Search by title"),
    marketplace_id: UUID | None = Query(None, description="Filter by marketplace UUID"),
    category: str | None = Query(None, description="Filter by marketplace domain/name"),
    sort: str = Query(
        "recent",
        description="recent|name_asc|name_desc|price_asc|price_desc|trending|gainers|losers|volatile",
    ),
    limit: int = Query(20, ge=1, le=PAGE_SIZE_MAX),
    offset: int = Query(0, ge=0, le=OFFSET_MAX),
    cursor: str | None = Query(
        None,
        description="Keyset cursor from next_cursor/prev_cursor; overrides offset.",
    ),
    skip_total: bool = Query(
        False,
        description="Skip the count query entirely; total comes back null (P12 typeahead).",
    ),
    display_currency: str = Query("local", description="local|EUR|USD"),
) -> PoolProductsResponse:
    service = ProductPoolService(db)
    items, total, page_meta = await service.list_products(
        sort=sort,
        search=search,
        marketplace_id=marketplace_id,
        category=category,
        limit=limit,
        offset=offset,
        cursor=cursor,
        skip_total=skip_total,
        display_currency=display_currency,
    )
    return PoolProductsResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        **page_meta,
    )


@router.get("/products/{listing_id}", response_model=PoolProductDetail)
async def get_pool_product(
    listing_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    _budget: PoolBudget,
    display_currency: str = Query("local", description="local|EUR|USD"),
) -> PoolProductDetail:
    """One product card by listing id (P2); 404 for hidden listings."""
    service = ProductPoolService(db)
    item = await service.get_product_detail(
        listing_id,
        display_currency=display_currency,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return PoolProductDetail(**item)


@router.get(
    "/products/{listing_id}/price-history",
    response_model=PriceHistoryResponse,
)
async def get_pool_product_price_history(
    listing_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    _budget: PoolBudget,
    period: Literal["7d", "30d", "90d"] = Query("30d"),
    bucket: Literal["day"] = Query("day"),
) -> PriceHistoryResponse:
    """Daily price series for one listing (P1); 404 for hidden listings."""
    _ = bucket
    service = ProductPoolService(db)
    history = await service.get_price_history(
        listing_id,
        period=period,
    )
    if history is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return PriceHistoryResponse(**history)


@router.get("/categories", response_model=list[PoolCategoryItem])
async def pool_categories(
    current_user: CurrentUser, db: DbSession, _budget: PoolBudget
) -> list[PoolCategoryItem]:
    service = ProductPoolService(db)
    rows = await service.get_categories()
    return [PoolCategoryItem(**row) for row in rows]


@router.get("/marketplace-stats", response_model=list[PoolCategorySummary])
async def pool_marketplace_stats(
    current_user: CurrentUser,
    db: DbSession,
    _budget: PoolBudget,
) -> list[PoolCategorySummary]:
    service = ProductPoolService(db)
    rows = await service.get_marketplace_stats()
    return [PoolCategorySummary(**row) for row in rows]


@router.get("/stats", response_model=PoolStatsResponse)
async def pool_stats(
    current_user: CurrentUser, db: DbSession, _budget: PoolBudget
) -> PoolStatsResponse:
    _ = current_user
    service = ProductPoolService(db)
    payload = await service.get_pool_stats()
    return PoolStatsResponse(**payload)

