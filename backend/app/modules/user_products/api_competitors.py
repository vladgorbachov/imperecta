"""Competitors API endpoints (v2 migration stub)."""

from uuid import UUID

from fastapi import APIRouter

from app.common.deps import CurrentUser, DbSession
from app.modules.marketplaces.api import MARKETPLACE_REGISTRY

router = APIRouter(prefix="/competitors", tags=["competitors"])

_MIG = "Endpoint pending migration to v2 schema"


@router.get("/marketplaces")
async def list_marketplaces(current_user: CurrentUser, db: DbSession) -> list[dict]:
    _ = current_user, db
    return [{"marketplace_id": reg["marketplace_id"], "name": reg["name"]} for reg in MARKETPLACE_REGISTRY]


@router.get("")
async def list_competitors(current_user: CurrentUser, db: DbSession) -> dict:
    _ = current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.post("")
async def create_competitor(current_user: CurrentUser, db: DbSession) -> dict:
    _ = current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.post("/products")
async def add_competitor_product(current_user: CurrentUser, db: DbSession) -> dict:
    _ = current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.get("/products/{product_id}")
async def list_competitor_products_by_product(product_id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    _ = product_id, current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.delete("/products/{id}")
async def delete_competitor_product(id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    _ = id, current_user, db
    return {"message": _MIG}


@router.get("/{competitor_id}")
async def get_competitor(competitor_id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    _ = competitor_id, current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.put("/{competitor_id}")
async def update_competitor(competitor_id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    _ = competitor_id, current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.delete("/{competitor_id}")
async def delete_competitor(competitor_id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    _ = competitor_id, current_user, db
    return {"message": _MIG}


@router.get("/{competitor_id}/products")
async def list_competitor_products_by_competitor(competitor_id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    _ = competitor_id, current_user, db
    return {"message": _MIG, "items": [], "total": 0}


@router.post("/{competitor_id}/scrape")
async def scrape_competitor(competitor_id: UUID, current_user: CurrentUser, db: DbSession) -> dict:
    _ = competitor_id, current_user, db
    return {"message": _MIG, "items": [], "total": 0}
