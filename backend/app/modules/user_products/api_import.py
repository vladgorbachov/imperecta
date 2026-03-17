"""Import/Export API endpoints."""

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.common.deps import CurrentUser, DbSession
from app.modules.ai_analyst.service import auto_categorize
from app.modules.core.plans.service import get_product_limit, is_free_plan
from app.modules.user_products.models import Product
from app.modules.user_products.service import (
    get_csv_template,
    parse_products_file,
    preview_products_file,
)

MAX_IMPORT_FILE_SIZE_BYTES = 5 * 1024 * 1024
router = APIRouter(prefix="/import", tags=["import"])


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


SUPPORTED_IMPORT_EXTENSIONS = (".csv", ".tsv", ".xls", ".xlsx", ".xlsm")


@router.post("/products/preview")
async def preview_products_csv(file: UploadFile, current_user: CurrentUser) -> dict:
    """Preview import from CSV, TSV, XLS, XLSX, or XLSM file."""
    _ = current_user
    content = await file.read(MAX_IMPORT_FILE_SIZE_BYTES + 1)
    if len(content) > MAX_IMPORT_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large.")
    preview, errors = preview_products_file(content, file.filename or "upload.csv", limit=5)
    return {"preview": preview, "errors": errors}


@router.post("/products/csv")
async def upload_products_csv(file: UploadFile, current_user: CurrentUser, db: DbSession) -> dict:
    """Import products from CSV, TSV, XLS, XLSX, or XLSM file."""
    content = await file.read(MAX_IMPORT_FILE_SIZE_BYTES + 1)
    if len(content) > MAX_IMPORT_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large.")
    filename = file.filename or "upload.csv"
    if not filename.lower().endswith(SUPPORTED_IMPORT_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Supported formats: {', '.join(SUPPORTED_IMPORT_EXTENSIONS)}",
        )
    products_data, errors = parse_products_file(content, filename, current_user.id)
    if errors and not products_data:
        return {"imported": 0, "errors": errors}

    if is_free_plan(current_user.plan):
        limit = get_product_limit(current_user.plan)
        count_result = await db.execute(select(func.count()).select_from(Product).where(Product.user_id == current_user.id))
        current_count = count_result.scalar() or 0
        slots = max(0, limit - current_count)
        if slots == 0:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Product limit reached.")
        products_data = products_data[:slots]

    imported = 0
    for data in products_data:
        db.add(
            Product(
                user_id=data["user_id"],
                name=data["name"],
                sku=data.get("sku"),
                current_price=data["current_price"],
                currency=data.get("currency", "RUB"),
                url=data.get("url"),
                category=data.get("category"),
            )
        )
        imported += 1
    await db.flush()
    return {"imported": imported, "errors": errors}


@router.get("/products/template")
async def download_products_template(current_user: CurrentUser) -> PlainTextResponse:
    _ = current_user
    return PlainTextResponse(
        content=get_csv_template(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products_template.csv"},
    )
