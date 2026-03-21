"""Import/Export API endpoints (v2 migration stub)."""

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.common.deps import CurrentUser, DbSession
from app.modules.ai_analyst.service import auto_categorize
from app.modules.user_products.service import (
    get_csv_template,
    preview_products_file,
)

MAX_IMPORT_FILE_SIZE_BYTES = 5 * 1024 * 1024
router = APIRouter(prefix="/import", tags=["import"])

SUPPORTED_IMPORT_EXTENSIONS = (".csv", ".tsv", ".xls", ".xlsx", ".xlsm")
_MIG = "Endpoint pending migration to v2 schema"


class AutoCategorizeProductItem(BaseModel):
    name: str | None = Field(None, max_length=500)
    sku: str | None = Field(None, max_length=100)
    price: float | None = Field(None, ge=0)


class AutoCategorizeRequest(BaseModel):
    products: list[AutoCategorizeProductItem] = Field(..., max_length=100)


@router.post("/auto-categorize")
async def post_auto_categorize(body: AutoCategorizeRequest, current_user: CurrentUser) -> list[dict]:
    _ = current_user
    items = [p.model_dump() for p in body.products]
    return await auto_categorize(items)


@router.post("/products/preview")
async def preview_products_csv(file: UploadFile, current_user: CurrentUser) -> dict:
    _ = current_user
    content = await file.read(MAX_IMPORT_FILE_SIZE_BYTES + 1)
    if len(content) > MAX_IMPORT_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large.")
    preview, errors = preview_products_file(content, file.filename or "upload.csv", limit=5)
    return {"preview": preview, "errors": errors}


@router.post("/products/csv")
async def upload_products_csv(file: UploadFile, current_user: CurrentUser, db: DbSession) -> dict:
    _ = file, current_user, db
    return {"imported": 0, "errors": [], "message": _MIG}


@router.get("/products/template")
async def download_products_template(current_user: CurrentUser) -> PlainTextResponse:
    _ = current_user
    return PlainTextResponse(
        content=get_csv_template(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products_template.csv"},
    )
