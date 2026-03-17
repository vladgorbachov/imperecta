"""Products API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.common.deps import CurrentUser, DbSession
from app.modules.core.plans.service import get_product_limit, is_free_plan
from app.modules.user_products.models import CompetitorProduct, Product
from app.modules.user_products.schemas import (
    CompetitorProductBrief,
    ProductCreate,
    ProductDetailResponse,
    ProductListItem,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/categories")
async def list_categories(current_user: CurrentUser, db: DbSession) -> list[str]:
    result = await db.execute(
        select(Product.category).where(Product.user_id == current_user.id, Product.category.isnot(None)).distinct()
    )
    return [row[0] for row in result.all() if row[0]]


@router.get("", response_model=ProductListResponse)
async def list_products(
    current_user: CurrentUser,
    db: DbSession,
    search: str | None = Query(None, description="Search by name or SKU"),
    category: str | None = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> ProductListResponse:
    query = select(Product).where(Product.user_id == current_user.id)
    count_query = select(func.count()).select_from(Product).where(Product.user_id == current_user.id)
    if search:
        search_pattern = f"%{search}%"
        query = query.where((Product.name.ilike(search_pattern)) | (Product.sku.ilike(search_pattern)))
        count_query = count_query.where((Product.name.ilike(search_pattern)) | (Product.sku.ilike(search_pattern)))
    if category:
        query = query.where(Product.category == category)
        count_query = count_query.where(Product.category == category)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    query = query.offset((page - 1) * limit).limit(limit).order_by(Product.created_at.desc())
    result = await db.execute(query)
    products = result.scalars().all()

    agg_result = await db.execute(
        select(
            Product.id,
            func.count(CompetitorProduct.id).label("cnt"),
            func.min(CompetitorProduct.last_price).label("min_price"),
            func.max(CompetitorProduct.last_price).label("max_price"),
            func.max(CompetitorProduct.last_checked_at).label("last_checked"),
        )
        .outerjoin(CompetitorProduct, CompetitorProduct.product_id == Product.id)
        .where(Product.id.in_(p.id for p in products))
        .group_by(Product.id)
    )
    agg_map = {row.id: row for row in agg_result}

    items: list[ProductListItem] = []
    for product in products:
        agg = agg_map.get(product.id)
        items.append(
            ProductListItem(
                id=product.id,
                user_id=product.user_id,
                name=product.name,
                sku=product.sku,
                current_price=product.current_price,
                currency=product.currency,
                url=product.url,
                category=product.category,
                is_active=product.is_active,
                competitor_count=agg.cnt if agg else 0,
                created_at=product.created_at,
                updated_at=product.updated_at,
                min_competitor_price=agg.min_price if agg else None,
                max_competitor_price=agg.max_price if agg else None,
                last_checked_at=agg.last_checked if agg else None,
            )
        )
    return ProductListResponse(items=items, total=total)


@router.get("/at-risk")
async def get_products_at_risk(current_user: CurrentUser, db: DbSession, limit: int = Query(5, ge=1, le=20)) -> list[dict]:
    from app.modules.ai_analyst.service import get_products_at_risk as get_at_risk

    return await get_at_risk(db, current_user.id, limit=limit)


@router.get("/{id}", response_model=ProductDetailResponse)
async def get_product(id: UUID, current_user: CurrentUser, db: DbSession) -> ProductDetailResponse:
    result = await db.execute(
        select(Product)
        .where(Product.id == id, Product.user_id == current_user.id)
        .options(selectinload(Product.competitor_products).selectinload(CompetitorProduct.competitor))
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    competitor_briefs = [
        {
            "id": cp.id,
            "competitor_id": cp.competitor_id,
            "competitor_name": cp.competitor.name,
            "marketplace": cp.competitor.marketplace,
            "url": cp.url,
            "name": cp.name,
            "last_price": cp.last_price,
            "last_promo_label": cp.last_promo_label,
            "last_in_stock": cp.last_in_stock,
            "last_checked_at": cp.last_checked_at,
        }
        for cp in product.competitor_products
    ]
    return ProductDetailResponse(
        id=product.id,
        user_id=product.user_id,
        name=product.name,
        sku=product.sku,
        current_price=product.current_price,
        currency=product.currency,
        url=product.url,
        category=product.category,
        is_active=product.is_active,
        created_at=product.created_at,
        updated_at=product.updated_at,
        competitor_products=[CompetitorProductBrief(**item) for item in competitor_briefs],
    )


@router.get("/{id}/ai-recommendation")
async def get_product_ai_recommendation(id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    from app.modules.ai_analyst.service import get_price_recommendation

    try:
        return await get_price_recommendation(db, id, current_user.id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductCreate, current_user: CurrentUser, db: DbSession) -> ProductResponse:
    if is_free_plan(current_user.plan):
        limit = get_product_limit(current_user.plan)
        count_result = await db.execute(select(func.count()).select_from(Product).where(Product.user_id == current_user.id))
        if (count_result.scalar() or 0) >= limit:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Product limit reached.")

    product = Product(
        user_id=current_user.id,
        name=data.name,
        sku=data.sku,
        current_price=data.current_price,
        currency=data.currency,
        url=data.url,
        category=data.category,
    )
    db.add(product)
    await db.flush()
    return ProductResponse(
        id=product.id,
        user_id=product.user_id,
        name=product.name,
        sku=product.sku,
        current_price=product.current_price,
        currency=product.currency,
        url=product.url,
        category=product.category,
        is_active=product.is_active,
        competitor_count=0,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.put("/{id}", response_model=ProductResponse)
async def update_product(id: UUID, data: ProductUpdate, current_user: CurrentUser, db: DbSession) -> ProductResponse:
    result = await db.execute(select(Product).where(Product.id == id, Product.user_id == current_user.id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    await db.flush()
    count_result = await db.execute(select(func.count()).where(CompetitorProduct.product_id == product.id))
    competitor_count = count_result.scalar() or 0
    return ProductResponse(
        id=product.id,
        user_id=product.user_id,
        name=product.name,
        sku=product.sku,
        current_price=product.current_price,
        currency=product.currency,
        url=product.url,
        category=product.category,
        is_active=product.is_active,
        competitor_count=competitor_count,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(id: UUID, current_user: CurrentUser, db: DbSession) -> None:
    result = await db.execute(select(Product).where(Product.id == id, Product.user_id == current_user.id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await db.delete(product)
