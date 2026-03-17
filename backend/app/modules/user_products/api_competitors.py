"""Competitors API endpoints."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.common.deps import CurrentUser, DbSession
from app.modules.marketplaces.api import MARKETPLACE_REGISTRY
from app.modules.marketplaces.models import AdminMarketplace
from app.modules.user_products.models import Competitor, CompetitorProduct, Product
from app.modules.user_products.schemas import (
    CompetitorCreate,
    CompetitorProductCreate,
    CompetitorProductResponse,
    CompetitorResponse,
    CompetitorUpdate,
)

router = APIRouter(prefix="/competitors", tags=["competitors"])


def _compute_price_diff(last_price: Decimal | None, user_price: Decimal) -> float | None:
    if last_price is None or user_price == 0:
        return None
    return round(float((last_price - user_price) / user_price * 100), 2)


@router.get("/marketplaces")
async def list_marketplaces(current_user: CurrentUser, db: DbSession) -> list[dict]:
    _ = current_user
    items = [{"marketplace_id": reg["marketplace_id"], "name": reg["name"]} for reg in MARKETPLACE_REGISTRY]
    result = await db.execute(select(AdminMarketplace.marketplace_id, AdminMarketplace.name).where(AdminMarketplace.is_active.is_(True)))
    seen = {row["marketplace_id"] for row in items}
    for row in result.all():
        if row.marketplace_id not in seen:
            items.append({"marketplace_id": row.marketplace_id, "name": row.name or row.marketplace_id})
    items.sort(key=lambda x: x["name"].lower())
    return items


@router.get("", response_model=list[CompetitorResponse])
async def list_competitors(current_user: CurrentUser, db: DbSession) -> list[CompetitorResponse]:
    result = await db.execute(
        select(Competitor, func.count(CompetitorProduct.id).label("product_count"))
        .outerjoin(CompetitorProduct, CompetitorProduct.competitor_id == Competitor.id)
        .where(Competitor.user_id == current_user.id)
        .group_by(Competitor.id)
    )
    return [
        CompetitorResponse(
            id=competitor.id,
            user_id=competitor.user_id,
            name=competitor.name,
            website_url=competitor.website_url,
            marketplace=competitor.marketplace,
            notes=competitor.notes,
            created_at=competitor.created_at,
            product_count=product_count,
        )
        for competitor, product_count in result.all()
    ]


@router.post("/", response_model=CompetitorResponse, status_code=status.HTTP_201_CREATED)
async def create_competitor(data: CompetitorCreate, current_user: CurrentUser, db: DbSession) -> CompetitorResponse:
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
async def update_competitor(id: UUID, data: CompetitorUpdate, current_user: CurrentUser, db: DbSession) -> CompetitorResponse:
    result = await db.execute(select(Competitor).where(Competitor.id == id, Competitor.user_id == current_user.id))
    competitor = result.scalar_one_or_none()
    if competitor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(competitor, key, value)
    await db.flush()
    count_result = await db.execute(select(func.count()).select_from(CompetitorProduct).where(CompetitorProduct.competitor_id == competitor.id))
    return CompetitorResponse(
        id=competitor.id,
        user_id=competitor.user_id,
        name=competitor.name,
        website_url=competitor.website_url,
        marketplace=competitor.marketplace,
        notes=competitor.notes,
        created_at=competitor.created_at,
        product_count=count_result.scalar() or 0,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor(id: UUID, current_user: CurrentUser, db: DbSession) -> None:
    result = await db.execute(select(Competitor).where(Competitor.id == id, Competitor.user_id == current_user.id))
    competitor = result.scalar_one_or_none()
    if competitor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")
    await db.delete(competitor)


@router.post("/products", response_model=CompetitorProductResponse, status_code=status.HTTP_201_CREATED)
async def add_competitor_product(data: CompetitorProductCreate, current_user: CurrentUser, db: DbSession) -> CompetitorProductResponse:
    product_result = await db.execute(select(Product).where(Product.id == data.product_id, Product.user_id == current_user.id))
    product = product_result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    competitor_result = await db.execute(select(Competitor).where(Competitor.id == data.competitor_id, Competitor.user_id == current_user.id))
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
        price_diff=_compute_price_diff(cp.last_price, product.current_price),
    )


@router.get("/products/{product_id}", response_model=list[CompetitorProductResponse])
async def list_competitor_products_by_product(product_id: UUID, current_user: CurrentUser, db: DbSession) -> list[CompetitorProductResponse]:
    product_result = await db.execute(
        select(Product)
        .where(Product.id == product_id, Product.user_id == current_user.id)
        .options(selectinload(Product.competitor_products).selectinload(CompetitorProduct.competitor))
    )
    product = product_result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return [
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
            price_diff=_compute_price_diff(cp.last_price, product.current_price),
        )
        for cp in product.competitor_products
    ]


@router.get("/{competitor_id}/products", response_model=list[CompetitorProductResponse])
async def list_competitor_products_by_competitor(competitor_id: UUID, current_user: CurrentUser, db: DbSession) -> list[CompetitorProductResponse]:
    competitor_result = await db.execute(
        select(Competitor)
        .where(Competitor.id == competitor_id, Competitor.user_id == current_user.id)
        .options(selectinload(Competitor.competitor_products).selectinload(CompetitorProduct.product))
    )
    competitor = competitor_result.scalar_one_or_none()
    if competitor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")
    return [
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
            price_diff=_compute_price_diff(cp.last_price, cp.product.current_price if cp.product else Decimal("0")),
        )
        for cp in competitor.competitor_products
    ]


@router.post("/products/{id}/scrape")
async def trigger_manual_competitor_product_scrape(id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    result = await db.execute(
        select(CompetitorProduct)
        .join(Product, CompetitorProduct.product_id == Product.id)
        .where(CompetitorProduct.id == id, Product.user_id == current_user.id)
    )
    cp = result.scalar_one_or_none()
    if cp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor product not found")
    from app.modules.scraper.tasks import scrape_single

    task = scrape_single.delay(str(cp.id))
    return {"status": "enqueued", "task_id": task.id, "competitor_product_id": str(cp.id)}


@router.delete("/products/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor_product(id: UUID, current_user: CurrentUser, db: DbSession) -> None:
    result = await db.execute(
        select(CompetitorProduct)
        .join(Product, CompetitorProduct.product_id == Product.id)
        .where(CompetitorProduct.id == id, Product.user_id == current_user.id)
    )
    cp = result.scalar_one_or_none()
    if cp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor product not found")
    await db.delete(cp)
