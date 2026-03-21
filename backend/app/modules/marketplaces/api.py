"""Marketplace pool admin API (v2 migration stubs)."""

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, HttpUrl

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser

router = APIRouter(
    prefix="/admin/marketplaces",
    tags=["marketplaces"],
    dependencies=[Depends(get_current_superuser)],
)

MARKETPLACE_REGISTRY: list[dict[str, Any]] = [
    {"marketplace_id": "ozon", "name": "Ozon", "domain": "ozon.ru", "country": "RU", "region": "cis"},
    {"marketplace_id": "wildberries", "name": "Wildberries", "domain": "wildberries.ru", "country": "RU", "region": "cis"},
    {"marketplace_id": "kaspi", "name": "Kaspi", "domain": "kaspi.kz", "country": "KZ", "region": "cis"},
]

_MSG = "Pending migration to v2 schema"


@router.post("/deduplicate")
async def deduplicate_marketplaces(
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> dict:
    return {"merged": 0, "deleted": 0, "message": _MSG}


@router.post("/recalculate-quotas")
async def recalculate_quotas(
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> dict:
    return {"status": "skipped", "message": _MSG}


@router.post("/set-requires-js")
async def set_requires_js(
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> dict:
    return {"status": "skipped", "message": _MSG}


@router.get("")
async def list_marketplaces(
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> list[dict]:
    return []


class AddMarketplaceBody(BaseModel):
    url: HttpUrl


@router.get("/{marketplace_id}/logs")
async def marketplace_logs(
    marketplace_id: str,
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> list[dict]:
    return []


@router.post("")
async def add_marketplace_placeholder() -> dict:
    raise HTTPException(status_code=501, detail=_MSG)


@router.post("/add-by-url")
async def add_by_url(
    body: AddMarketplaceBody,
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> dict:
    raise HTTPException(status_code=501, detail=_MSG)


@router.post("/import-file")
async def import_file(
    db: DbSession,
    _current_user: CurrentSuperuser,
    file: UploadFile = File(...),
) -> dict:
    raise HTTPException(status_code=501, detail=_MSG)


@router.delete("/{marketplace_id}")
async def delete_marketplace(
    marketplace_id: str,
    db: DbSession,
    _current_user: CurrentSuperuser,
) -> dict:
    raise HTTPException(status_code=501, detail=_MSG)
