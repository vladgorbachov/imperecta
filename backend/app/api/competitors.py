"""Competitors API endpoints."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models import Competitor, CompetitorProduct, Product
from app.schemas.competitor import (
    CompetitorCreate,
    CompetitorProductCreate,
    CompetitorProductResponse,
    CompetitorResponse,
    CompetitorUpdate,
)

router = APIRouter()


def _compute_price_diff(
    last_price: Decimal | None,
    user_price: Decimal,
) -> float | None:
    """Compute price difference in percent. Positive = competitor more expensive."""
    if last_price is None or user_price == 0:
        return None
    diff = float((last_price - user_price) / user_price * 100)
    return round(diff, 2)


@router.get("", response_model=list[CompetitorResponse])
async def list_competitors(
    current_user: CurrentUser,
    db: DbSession,
) -> list[CompetitorResponse]:
    """List competitors of current user with product count."""
    result = await db.execute(
        select(
            Competitor,
            func.count(CompetitorProduct.id).label("product_count"),
        )
        .outerjoin(CompetitorProduct, CompetitorProduct.competitor_id == Competitor.id)
        .where(Competitor.user_id == current_user.id)
        .group_by(Competitor.id)
    )
    rows = result.all()
    return [
        CompetitorResponse(
            id=c.id,
            user_id=c.user_id,
            name=c.name,
            website_url=c.website_url,
            marketplace=c.marketplace,
            notes=c.notes,
            created_at=c.created_at,
            product_count=pc,
        )
        for c, pc in rows
    ]


@router.post("/", response_model=CompetitorResponse, status_code=status.HTTP_201_CREATED)
async def create_competitor(
    data: CompetitorCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> CompetitorResponse:
    """Create new competitor."""
    competitor = Competitor(
        user_id=current_user.id,
        name=data.name,
        website_url=data.website_url,
        marketplace=data.marketplace,
        notes=data.notes,
    )
    db.add(competitor)
    await db.flush()
    return CompetitorResponse(
        id=competitor.id,
        user_id=competitor.user_id,
        name=competitor.name,
        website_url=competitor.website_url,
        marketplace=competitor.marketplace,
        notes=competitor.notes,
        created_at=competitor.created_at,
        product_count=0,
    )


@router.put("/{id}", response_model=CompetitorResponse)
async def update_competitor(
    id: UUID,
    data: CompetitorUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> CompetitorResponse:
    """Update competitor."""
    result = await db.execute(
        select(Competitor).where(
            Competitor.id == id,
            Competitor.user_id == current_user.id,
        )
    )
    competitor = result.scalar_one_or_none()
    if competitor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(competitor, key, value)

    await db.flush()
    count_result = await db.execute(
        select(func.count()).select_from(CompetitorProduct).where(
            CompetitorProduct.competitor_id == competitor.id
        )
    )
    product_count = count_result.scalar() or 0
    return CompetitorResponse(
        id=competitor.id,
        user_id=competitor.user_id,
        name=competitor.name,
        website_url=competitor.website_url,
        marketplace=competitor.marketplace,
        notes=competitor.notes,
        created_at=competitor.created_at,
        product_count=product_count,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor(
    id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete competitor."""
    result = await db.execute(
        select(Competitor).where(
            Competitor.id == id,
            Competitor.user_id == current_user.id,
        )
    )
    competitor = result.scalar_one_or_none()
    if competitor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    await db.delete(competitor)


@router.post("/products", response_model=CompetitorProductResponse, status_code=status.HTTP_201_CREATED)
async def add_competitor_product(
    data: CompetitorProductCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> CompetitorProductResponse:
    """Add competitor product (link URL to product + competitor)."""
    product_result = await db.execute(
        select(Product).where(
            Product.id == data.product_id,
            Product.user_id == current_user.id,
        )
    )
    product = product_result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    competitor_result = await db.execute(
        select(Competitor).where(
            Competitor.id == data.competitor_id,
            Competitor.user_id == current_user.id,
        )
    )
    competitor = competitor_result.scalar_one_or_none()
    if competitor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    cp = CompetitorProduct(
        product_id=data.product_id,
        competitor_id=data.competitor_id,
        url=data.url,
        name=data.name,
        scraper_type=data.scraper_type,
        css_selector_price=data.css_selector_price,
    )
    db.add(cp)
    await db.flush()

    price_diff = _compute_price_diff(cp.last_price, product.current_price)

    return CompetitorProductResponse(
        id=cp.id,
        product_id=cp.product_id,
        competitor_id=cp.competitor_id,
        competitor_name=competitor.name,
        url=cp.url,
        name=cp.name,
        last_price=cp.last_price,
        last_promo_label=cp.last_promo_label,
        last_in_stock=cp.last_in_stock,
        last_checked_at=cp.last_checked_at,
        scraper_type=cp.scraper_type,
        css_selector_price=cp.css_selector_price,
        is_active=cp.is_active,
        created_at=cp.created_at,
        price_diff=price_diff,
    )


@router.get("/products/{product_id}", response_model=list[CompetitorProductResponse])
async def list_competitor_products_by_product(
    product_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[CompetitorProductResponse]:
    """List all competitor products for given product."""
    product_result = await db.execute(
        select(Product)
        .where(
            Product.id == product_id,
            Product.user_id == current_user.id,
        )
        .options(
            selectinload(Product.competitor_products).selectinload(CompetitorProduct.competitor)
        )
    )
    product = product_result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    result = []
    for cp in product.competitor_products:
        price_diff = _compute_price_diff(cp.last_price, product.current_price)
        result.append(
            CompetitorProductResponse(
                id=cp.id,
                product_id=cp.product_id,
                competitor_id=cp.competitor_id,
                competitor_name=cp.competitor.name,
                url=cp.url,
                name=cp.name,
                last_price=cp.last_price,
                last_promo_label=cp.last_promo_label,
                last_in_stock=cp.last_in_stock,
                last_checked_at=cp.last_checked_at,
                scraper_type=cp.scraper_type,
                css_selector_price=cp.css_selector_price,
                is_active=cp.is_active,
                created_at=cp.created_at,
                price_diff=price_diff,
            )
        )
    return result


@router.get("/{competitor_id}/products", response_model=list[CompetitorProductResponse])
async def list_competitor_products_by_competitor(
    competitor_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[CompetitorProductResponse]:
    """List competitor products for given competitor."""
    competitor_result = await db.execute(
        select(Competitor)
        .where(
            Competitor.id == competitor_id,
            Competitor.user_id == current_user.id,
        )
        .options(
            selectinload(Competitor.competitor_products).selectinload(CompetitorProduct.product)
        )
    )
    competitor = competitor_result.scalar_one_or_none()
    if competitor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    result = []
    for cp in competitor.competitor_products:
        user_price = cp.product.current_price if cp.product else Decimal("0")
        price_diff = _compute_price_diff(cp.last_price, user_price)
        result.append(
            CompetitorProductResponse(
                id=cp.id,
                product_id=cp.product_id,
                competitor_id=cp.competitor_id,
                competitor_name=competitor.name,
                url=cp.url,
                name=cp.name,
                last_price=cp.last_price,
                last_promo_label=cp.last_promo_label,
                last_in_stock=cp.last_in_stock,
                last_checked_at=cp.last_checked_at,
                scraper_type=cp.scraper_type,
                css_selector_price=cp.css_selector_price,
                is_active=cp.is_active,
                created_at=cp.created_at,
                price_diff=price_diff,
            )
        )
    return result




@router.delete("/products/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor_product(
    id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """Remove competitor product link."""
    result = await db.execute(
        select(CompetitorProduct)
        .join(Product, CompetitorProduct.product_id == Product.id)
        .where(
            CompetitorProduct.id == id,
            Product.user_id == current_user.id,
        )
    )
    cp = result.scalar_one_or_none()
    if cp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor product not found")

    await db.delete(cp)
