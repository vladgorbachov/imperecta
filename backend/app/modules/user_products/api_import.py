"""Import/Export API endpoints."""

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.common.deps import CurrentUser, DbSession
from app.models.core import UserProduct
from app.models.dimensions import DimProduct
from app.modules.ai_analyst.service import auto_categorize
from app.modules.user_products.service import (
    get_csv_template,
    parse_products_file,
    preview_products_file,
)

MAX_IMPORT_FILE_SIZE_BYTES = 5 * 1024 * 1024
router = APIRouter(prefix="/import", tags=["import"])

SUPPORTED_IMPORT_EXTENSIONS = (".csv", ".tsv", ".xls", ".xlsx", ".xlsm")


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
    filename = file.filename or "upload.csv"
    if not filename.lower().endswith(SUPPORTED_IMPORT_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Unsupported file format.")
    content = await file.read(MAX_IMPORT_FILE_SIZE_BYTES + 1)
    if len(content) > MAX_IMPORT_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large.")
    products_to_create, errors = parse_products_file(
        content=content,
        filename=filename,
        user_id=current_user.id,
        currency_code=current_user.default_currency,
    )
    imported = 0
    for item in products_to_create:
        normalized_name = str(item["name"]).strip()
        sku = item.get("sku")
        existing_product = await db.scalar(
            select(DimProduct).where(
                DimProduct.name_normalized == normalized_name.lower(),
                DimProduct.sku_universal == sku,
            )
        )
        if existing_product is None:
            existing_product = DimProduct(
                name=normalized_name,
                name_normalized=normalized_name.lower(),
                sku_universal=sku,
                attributes={"category": item.get("category")} if item.get("category") else {},
                is_active=True,
            )
            db.add(existing_product)
            await db.flush()
        existing_link = await db.scalar(
            select(UserProduct.id).where(
                UserProduct.user_id == current_user.id,
                UserProduct.product_id == existing_product.id,
            )
        )
        if existing_link is not None:
            continue
        db.add(
            UserProduct(
                user_id=current_user.id,
                product_id=existing_product.id,
                custom_name=normalized_name,
                custom_sku=sku,
                target_price=item["current_price"],
                currency_code=item["currency"],
                is_active=True,
            )
        )
        imported += 1
    await db.commit()
    return {"imported": imported, "errors": errors}


@router.get("/products/template")
async def download_products_template(current_user: CurrentUser) -> PlainTextResponse:
    _ = current_user
    return PlainTextResponse(
        content=get_csv_template(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products_template.csv"},
    )
