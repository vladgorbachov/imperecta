"""Products API endpoints (v2 migration stub)."""

from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.common.deps import CurrentUser, DbSession
from app.modules.user_products.schemas import ProductCreate, ProductListResponse, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])

_MIG = "Endpoint pending migration to v2 schema"


class BulkDeleteBody(BaseModel):
    product_ids: list[UUID]


@router.get("/categories")
async def list_categories(current_user: CurrentUser, db: DbSession) -> list[str]:
    _ = current_user, db
    return []


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
) -> ProductListResponse:
    _ = current_user, db, search, category, sort, page, limit
    return ProductListResponse(items=[], total=0)


@router.get("/at-risk")
async def get_products_at_risk(current_user: CurrentUser, db: DbSession, limit: int = Query(5, ge=1, le=20)) -> list[dict]:
    _ = current_user, db, limit
    return []


@router.post("/")
async def create_product(data: ProductCreate, current_user: CurrentUser, db: DbSession) -> dict:
    _ = data, current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.delete("/bulk")
async def bulk_delete_products(body: BulkDeleteBody, current_user: CurrentUser, db: DbSession) -> dict:
    _ = body, current_user, db
    return {"deleted": 0, "message": _MIG}


@router.delete("/all")
async def delete_all_user_products(current_user: CurrentUser, db: DbSession) -> dict:
    _ = current_user, db
    return {"deleted": 0, "message": _MIG}


@router.get("/{id}")
async def get_product(id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    _ = id, current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.get("/{id}/ai-recommendation")
async def get_product_ai_recommendation(id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    _ = id, current_user, db
    return {"message": _MIG, "recommended_price": None}


@router.put("/{id}")
async def update_product(id: UUID, data: ProductUpdate, current_user: CurrentUser, db: DbSession) -> dict:
    _ = id, data, current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.delete("/{id}")
async def delete_product(id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    _ = id, current_user, db
    return {"message": _MIG}
