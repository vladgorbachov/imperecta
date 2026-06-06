"""Products API endpoints."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select

from app.common.currency import (
    DISPLAY_LOCAL,
    CurrencyConverter,
    display_price_fields,
    normalize_display_currency,
)
from app.common.deps import CurrentUser, DbSession
from app.models.core import UserProduct
from app.models.dimensions import DimProduct
from app.models.facts import FactListing
from app.modules.user_products.schemas import (
    ProductCreate,
    ProductDetailResponse,
    ProductListItem,
    ProductListResponse,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["products"])


class BulkDeleteBody(BaseModel):
    product_ids: list[UUID]


@router.get("/categories")
async def list_categories(current_user: CurrentUser, db: DbSession) -> list[str]:
    category_expr = DimProduct.attributes["category"].astext
    result = await db.execute(
        select(category_expr)
        .select_from(UserProduct)
        .join(DimProduct, DimProduct.id == UserProduct.product_id)
        .where(
            UserProduct.user_id == current_user.id,
            UserProduct.is_active.is_(True),
            category_expr.is_not(None),
            category_expr != "",
        )
        .group_by(category_expr)
        .order_by(category_expr.asc())
    )
    return [str(row[0]) for row in result.all() if row[0]]


@router.get("", response_model=ProductListResponse)
async def list_products(
    current_user: CurrentUser,
    db: DbSession,
    search: str | None = Query(None, description="Search by name or SKU"),
    category: str | None = Query(None, description="Filter by category"),
    sort: str = Query(
        "recent",
        description="recent|name_asc|name_desc|price_asc|price_desc",
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    display_currency: str = Query("local", description="local|EUR|USD"),
) -> ProductListResponse:
    listing_stats_sq = (
        select(
            FactListing.product_id.label("product_id"),
            func.min(FactListing.last_price).label("min_comp_price"),
            func.max(FactListing.last_price).label("max_comp_price"),
            func.max(FactListing.last_checked_at).label("last_checked_at"),
            func.min(FactListing.last_currency_code).label("currency_code"),
        )
        .where(FactListing.is_active.is_(True))
        .group_by(FactListing.product_id)
        .subquery()
    )
    category_expr = DimProduct.attributes["category"].astext
    filters: list[Any] = [
        UserProduct.user_id == current_user.id,
        UserProduct.is_active.is_(True),
        DimProduct.is_active.is_(True),
    ]
    if search:
        like = f"%{search.strip()}%"
        filters.append(
            (
                DimProduct.name.ilike(like)
                | DimProduct.name_normalized.ilike(like)
                | DimProduct.sku_universal.ilike(like)
                | UserProduct.custom_name.ilike(like)
                | UserProduct.custom_sku.ilike(like)
            )
        )
    if category:
        filters.append(category_expr == category)

    base_stmt = (
        select(
            DimProduct.id.label("id"),
            UserProduct.user_id.label("user_id"),
            UserProduct.custom_name.label("custom_name"),
            UserProduct.custom_sku.label("custom_sku"),
            UserProduct.target_price.label("target_price"),
            UserProduct.currency_code.label("target_currency"),
            UserProduct.created_at.label("created_at"),
            UserProduct.updated_at.label("updated_at"),
            DimProduct.name.label("product_name"),
            DimProduct.sku_universal.label("sku_universal"),
            category_expr.label("category"),
            listing_stats_sq.c.min_comp_price,
            listing_stats_sq.c.max_comp_price,
            listing_stats_sq.c.last_checked_at,
            listing_stats_sq.c.currency_code.label("listing_currency"),
        )
        .select_from(UserProduct)
        .join(DimProduct, DimProduct.id == UserProduct.product_id)
        .outerjoin(listing_stats_sq, listing_stats_sq.c.product_id == DimProduct.id)
        .where(and_(*filters))
    )
    total = int((await db.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar() or 0)

    sort_key = (sort or "recent").lower()
    if sort_key == "name_asc":
        base_stmt = base_stmt.order_by(DimProduct.name.asc())
    elif sort_key == "name_desc":
        base_stmt = base_stmt.order_by(DimProduct.name.desc())
    elif sort_key == "price_asc":
        base_stmt = base_stmt.order_by(UserProduct.target_price.asc().nullslast())
    elif sort_key == "price_desc":
        base_stmt = base_stmt.order_by(UserProduct.target_price.desc().nullslast())
    else:
        base_stmt = base_stmt.order_by(UserProduct.created_at.desc().nullslast())

    offset = max(page - 1, 0) * limit
    rows = (await db.execute(base_stmt.offset(offset).limit(limit))).mappings().all()

    target_currency = normalize_display_currency(display_currency)
    converter = (
        await CurrencyConverter.load_latest(db)
        if target_currency != DISPLAY_LOCAL
        else None
    )

    items: list[ProductListItem] = []
    for row in rows:
        current_price = row["target_price"] or row["min_comp_price"] or row["max_comp_price"]
        if current_price is None:
            # Do not mask missing prices with defaults; skip invalid entries.
            continue
        currency = row["target_currency"] or row["listing_currency"] or "EUR"
        listing_currency = row["listing_currency"] or currency
        display_value, display_code, conversion_available = display_price_fields(
            current_price, currency, target_currency, converter
        )
        min_display, _, _ = display_price_fields(
            row["min_comp_price"], listing_currency, target_currency, converter
        )
        max_display, _, _ = display_price_fields(
            row["max_comp_price"], listing_currency, target_currency, converter
        )
        items.append(
            ProductListItem(
                id=row["id"],
                user_id=row["user_id"],
                name=row["custom_name"] or row["product_name"],
                sku=row["custom_sku"] or row["sku_universal"],
                current_price=Decimal(str(current_price)),
                currency=currency,
                url=None,
                category=row["category"],
                is_active=True,
                competitor_count=0,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                min_competitor_price=(
                    Decimal(str(row["min_comp_price"])) if row["min_comp_price"] is not None else None
                ),
                max_competitor_price=(
                    Decimal(str(row["max_comp_price"])) if row["max_comp_price"] is not None else None
                ),
                display_price=display_value,
                display_currency=display_code,
                conversion_available=conversion_available,
                min_competitor_display_price=min_display,
                max_competitor_display_price=max_display,
                last_checked_at=row["last_checked_at"],
            )
        )
    return ProductListResponse(items=items, total=total)


@router.get("/at-risk")
async def get_products_at_risk(current_user: CurrentUser, db: DbSession, limit: int = Query(5, ge=1, le=20)) -> list[dict]:
    listing_errors_sq = (
        select(
            FactListing.product_id.label("product_id"),
            func.max(FactListing.consecutive_errors).label("max_errors"),
            func.max(FactListing.last_checked_at).label("last_checked_at"),
        )
        .where(FactListing.is_active.is_(True))
        .group_by(FactListing.product_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(
                DimProduct.id,
                DimProduct.name,
                listing_errors_sq.c.max_errors,
                listing_errors_sq.c.last_checked_at,
            )
            .select_from(UserProduct)
            .join(DimProduct, DimProduct.id == UserProduct.product_id)
            .join(listing_errors_sq, listing_errors_sq.c.product_id == DimProduct.id)
            .where(
                UserProduct.user_id == current_user.id,
                UserProduct.is_active.is_(True),
                listing_errors_sq.c.max_errors >= 5,
            )
            .order_by(listing_errors_sq.c.max_errors.desc(), listing_errors_sq.c.last_checked_at.desc())
            .limit(limit)
        )
    ).mappings().all()
    return [
        {
            "product_id": str(row["id"]),
            "name": row["name"],
            "consecutive_errors": int(row["max_errors"] or 0),
            "last_checked_at": row["last_checked_at"],
        }
        for row in rows
    ]


@router.post("/")
async def create_product(data: ProductCreate, current_user: CurrentUser, db: DbSession) -> dict:
    normalized_name = data.name.strip()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Product name is required")
    dim_product = DimProduct(
        name=normalized_name,
        name_normalized=normalized_name.lower(),
        sku_universal=data.sku.strip() if data.sku else None,
        attributes={"category": data.category} if data.category else {},
        is_active=True,
    )
    db.add(dim_product)
    await db.flush()
    existing_link = await db.scalar(
        select(UserProduct.id).where(
            UserProduct.user_id == current_user.id,
            UserProduct.product_id == dim_product.id,
        )
    )
    if existing_link is not None:
        raise HTTPException(status_code=409, detail="Product already tracked")
    user_product = UserProduct(
        user_id=current_user.id,
        product_id=dim_product.id,
        custom_name=normalized_name,
        custom_sku=data.sku.strip() if data.sku else None,
        target_price=data.current_price,
        currency_code=(data.currency or "EUR").upper(),
        is_active=True,
    )
    db.add(user_product)
    await db.commit()
    return {
        "id": str(dim_product.id),
        "user_id": str(current_user.id),
        "name": normalized_name,
        "sku": user_product.custom_sku,
        "current_price": float(data.current_price),
        "currency": user_product.currency_code,
        "url": data.url,
        "category": data.category,
        "is_active": True,
        "competitor_count": 0,
        "created_at": user_product.created_at,
        "updated_at": user_product.updated_at,
    }


@router.delete("/bulk")
async def bulk_delete_products(body: BulkDeleteBody, current_user: CurrentUser, db: DbSession) -> dict:
    if not body.product_ids:
        return {"deleted": 0}
    result = await db.execute(
        select(UserProduct).where(
            UserProduct.user_id == current_user.id,
            UserProduct.product_id.in_(body.product_ids),
        )
    )
    rows = result.scalars().all()
    for row in rows:
        await db.delete(row)
    await db.commit()
    return {"deleted": len(rows)}


@router.delete("/all")
async def delete_all_user_products(current_user: CurrentUser, db: DbSession) -> dict:
    result = await db.execute(select(UserProduct).where(UserProduct.user_id == current_user.id))
    rows = result.scalars().all()
    for row in rows:
        await db.delete(row)
    await db.commit()
    return {"deleted": len(rows)}


@router.get("/{id}")
async def get_product(id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    row = (
        await db.execute(
            select(UserProduct, DimProduct)
            .join(DimProduct, DimProduct.id == UserProduct.product_id)
            .where(
                UserProduct.user_id == current_user.id,
                UserProduct.product_id == id,
                UserProduct.is_active.is_(True),
            )
            .limit(1)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    user_product, dim_product = row
    latest_listing = (
        await db.execute(
            select(FactListing.last_price, FactListing.last_currency_code)
            .where(
                FactListing.product_id == dim_product.id,
                FactListing.last_price.is_not(None),
                FactListing.is_active.is_(True),
            )
            .order_by(FactListing.last_checked_at.desc().nullslast())
            .limit(1)
        )
    ).first()
    current_price = user_product.target_price or (latest_listing[0] if latest_listing else None)
    if current_price is None:
        raise HTTPException(status_code=400, detail="Product has no price data")
    currency = user_product.currency_code or (latest_listing[1] if latest_listing else None) or "EUR"
    return ProductDetailResponse(
        id=dim_product.id,
        user_id=current_user.id,
        name=user_product.custom_name or dim_product.name,
        sku=user_product.custom_sku or dim_product.sku_universal,
        current_price=Decimal(str(current_price)),
        currency=currency,
        url=None,
        category=(dim_product.attributes or {}).get("category"),
        is_active=bool(user_product.is_active),
        created_at=user_product.created_at,
        updated_at=user_product.updated_at,
        competitor_products=[],
    ).model_dump()


@router.get("/{id}/ai-recommendation")
async def get_product_ai_recommendation(id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    row = (
        await db.execute(
            select(UserProduct.target_price)
            .where(UserProduct.user_id == current_user.id, UserProduct.product_id == id)
            .limit(1)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    current_price = row[0]
    market_min = await db.scalar(
        select(func.min(FactListing.last_price)).where(
            FactListing.product_id == id,
            FactListing.last_price.is_not(None),
            FactListing.is_active.is_(True),
        )
    )
    if current_price is None or market_min is None:
        return {"recommended_price": None, "reason": "insufficient_market_data"}
    recommended = min(Decimal(str(current_price)), Decimal(str(market_min)))
    return {"recommended_price": float(recommended), "reason": "aligned_to_market_min"}


@router.put("/{id}")
async def update_product(id: UUID, data: ProductUpdate, current_user: CurrentUser, db: DbSession) -> dict:
    row = (
        await db.execute(
            select(UserProduct, DimProduct)
            .join(DimProduct, DimProduct.id == UserProduct.product_id)
            .where(UserProduct.user_id == current_user.id, UserProduct.product_id == id)
            .limit(1)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    user_product, dim_product = row
    if data.name is not None:
        normalized_name = data.name.strip()
        if not normalized_name:
            raise HTTPException(status_code=400, detail="Product name cannot be empty")
        user_product.custom_name = normalized_name
        dim_product.name = normalized_name
        dim_product.name_normalized = normalized_name.lower()
    if data.sku is not None:
        cleaned = data.sku.strip() if data.sku else None
        user_product.custom_sku = cleaned
        dim_product.sku_universal = cleaned
    if data.current_price is not None:
        user_product.target_price = data.current_price
    if data.currency is not None:
        user_product.currency_code = data.currency.upper()
    if data.category is not None:
        attributes = dict(dim_product.attributes or {})
        if data.category:
            attributes["category"] = data.category
        else:
            attributes.pop("category", None)
        dim_product.attributes = attributes
    if data.is_active is not None:
        user_product.is_active = bool(data.is_active)
    await db.commit()
    return {"updated": True}


@router.delete("/{id}")
async def delete_product(id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    user_product = await db.scalar(
        select(UserProduct).where(
            UserProduct.user_id == current_user.id,
            UserProduct.product_id == id,
        )
    )
    if user_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(user_product)
    await db.commit()
    return {"deleted": True}
