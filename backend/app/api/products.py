"""Products API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models import CompetitorProduct, Product
from app.schemas.product import (
    ProductCreate,
    ProductDetailResponse,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)

router = APIRouter()


@router.get("/", response_model=ProductListResponse)
async def list_products(
    current_user: CurrentUser,
    db: DbSession,
    search: str | None = Query(None, description="Search by name or SKU"),
    category: str | None = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> ProductListResponse:
    """List products of current user with pagination and filters."""
    query = select(Product).where(Product.user_id == current_user.id)
    count_query = select(func.count()).select_from(Product).where(
        Product.user_id == current_user.id
    )

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (Product.name.ilike(search_pattern)) | (Product.sku.ilike(search_pattern))
        )
        count_query = count_query.where(
            (Product.name.ilike(search_pattern)) | (Product.sku.ilike(search_pattern))
        )
    if category:
        query = query.where(Product.category == category)
        count_query = count_query.where(Product.category == category)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * limit).limit(limit).order_by(Product.created_at.desc())
    result = await db.execute(query)
    products = result.scalars().all()

    competitor_counts = await db.execute(
        select(Product.id, func.count(CompetitorProduct.id).label("cnt"))
        .outerjoin(CompetitorProduct, CompetitorProduct.product_id == Product.id)
        .where(Product.id.in_(p.id for p in products))
        .group_by(Product.id)
    )
    count_map = {row.id: row.cnt for row in competitor_counts}

    items = [
        ProductResponse(
            id=p.id,
            user_id=p.user_id,
            name=p.name,
            sku=p.sku,
            current_price=p.current_price,
            currency=p.currency,
            url=p.url,
            category=p.category,
            is_active=p.is_active,
            competitor_count=count_map.get(p.id, 0),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in products
    ]

    return ProductListResponse(items=items, total=total)


@router.get("/{id}", response_model=ProductDetailResponse)
async def get_product(
    id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ProductDetailResponse:
    """Get product details with competitor products list."""
    result = await db.execute(
        select(Product)
        .where(Product.id == id, Product.user_id == current_user.id)
        .options(selectinload(Product.competitor_products).selectinload(CompetitorProduct.competitor))
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    competitor_briefs = []
    for cp in product.competitor_products:
        competitor_briefs.append(
            {
                "id": cp.id,
                "competitor_id": cp.competitor_id,
                "competitor_name": cp.competitor.name,
                "url": cp.url,
                "name": cp.name,
                "last_price": cp.last_price,
                "last_checked_at": cp.last_checked_at,
            }
        )

    from app.schemas.product import CompetitorProductBrief

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
        competitor_products=[CompetitorProductBrief(**b) for b in competitor_briefs],
    )


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> ProductResponse:
    """Create new product."""
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
async def update_product(
    id: UUID,
    data: ProductUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> ProductResponse:
    """Update product."""
    result = await db.execute(
        select(Product).where(Product.id == id, Product.user_id == current_user.id)
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    await db.flush()

    count_result = await db.execute(
        select(func.count()).where(CompetitorProduct.product_id == product.id)
    )
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
async def delete_product(
    id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete product (cascade deletes competitor products)."""
    result = await db.execute(
        select(Product).where(Product.id == id, Product.user_id == current_user.id)
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    await db.delete(product)
