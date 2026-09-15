"""Public API for the global product pool."""

import csv
import io
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.common.deps import CurrentUser, DbSession
from app.modules.product_pool.schemas import (
    PoolCategoryItem,
    PoolCategorySummary,
    PoolProductDetail,
    PoolProductsResponse,
    PoolStatsResponse,
    PriceHistoryResponse,
)
from app.modules.product_pool.service import ProductPoolService

router = APIRouter(prefix="/pool", tags=["product-pool"])
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
) -> PoolProductsResponse:
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


_EXPORT_COLUMNS = [
    "title",
    "marketplace",
    "country",
    "price",
    "currency",
    "price_eur",
    "change_24h_pct",
    "in_stock",
    "last_checked_at",
    "url",
]


@router.get("/products/export.csv")
async def export_pool_products_csv(
    current_user: CurrentUser,
    db: DbSession,
    search: str | None = Query(None, min_length=2),
    marketplace_id: UUID | None = Query(None),
    category: str | None = Query(None),
    sort: str = Query("recent"),
) -> StreamingResponse:
    """Stream the FULL filtered pool as CSV (P5) — not just one page."""
    service = ProductPoolService(db)

    async def _generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(_EXPORT_COLUMNS)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        async for item in service.iter_export_rows(
            sort=sort,
            search=search,
            marketplace_id=marketplace_id,
            category=category,
            include_blocked_countries=bool(getattr(current_user, "is_superuser", False)),
        ):
            writer.writerow(
                [
                    item.get("title") or "",
                    item.get("marketplace_name") or "",
                    item.get("country_code") or "",
                    item.get("price") if item.get("price") is not None else "",
                    item.get("currency") or "",
                    item.get("price_eur") if item.get("price_eur") is not None else "",
                    item.get("price_change_pct")
                    if item.get("price_change_pct") is not None
                    else "",
                    item.get("in_stock") if item.get("in_stock") is not None else "",
                    item.get("last_checked_at").isoformat()
                    if item.get("last_checked_at")
                    else "",
                    item.get("url") or "",
                ]
            )
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    return StreamingResponse(
        _generate(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="imperecta_pool.csv"'},
    )


@router.get("/products/{listing_id}", response_model=PoolProductDetail)
async def get_pool_product(
    listing_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    display_currency: str = Query("local", description="local|EUR|USD"),
) -> PoolProductDetail:
    """One product card by listing id (P2); 404 for hidden/blocked listings."""
    service = ProductPoolService(db)
    item = await service.get_product_detail(
        listing_id,
        include_blocked_countries=bool(getattr(current_user, "is_superuser", False)),
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
    period: Literal["7d", "30d", "90d"] = Query("30d"),
    bucket: Literal["day"] = Query("day"),
) -> PriceHistoryResponse:
    """Daily price series for one listing (P1); 404 for hidden listings."""
    _ = bucket
    service = ProductPoolService(db)
    history = await service.get_price_history(
        listing_id,
        period=period,
        include_blocked_countries=bool(getattr(current_user, "is_superuser", False)),
    )
    if history is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return PriceHistoryResponse(**history)


@router.get("/categories", response_model=list[PoolCategoryItem])
async def pool_categories(current_user: CurrentUser, db: DbSession) -> list[PoolCategoryItem]:
    service = ProductPoolService(db)
    rows = await service.get_categories(
        include_blocked_countries=bool(getattr(current_user, "is_superuser", False)),
    )
    return [PoolCategoryItem(**row) for row in rows]


@router.get("/marketplace-stats", response_model=list[PoolCategorySummary])
async def pool_marketplace_stats(
    current_user: CurrentUser,
    db: DbSession,
) -> list[PoolCategorySummary]:
    service = ProductPoolService(db)
    rows = await service.get_marketplace_stats(
        include_blocked_countries=bool(getattr(current_user, "is_superuser", False)),
    )
    return [PoolCategorySummary(**row) for row in rows]


@router.get("/stats", response_model=PoolStatsResponse)
async def pool_stats(current_user: CurrentUser, db: DbSession) -> PoolStatsResponse:
    _ = current_user
    service = ProductPoolService(db)
    payload = await service.get_pool_stats()
    return PoolStatsResponse(**payload)

