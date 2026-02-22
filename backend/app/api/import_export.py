"""Import/Export API endpoints."""

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import PlainTextResponse

from app.api.deps import CurrentUser, DbSession
from app.models import Product
from app.services.import_service import (
    get_csv_template,
    parse_products_file,
    preview_products_file,
)

router = APIRouter()


@router.post("/products/preview")
async def preview_products_csv(
    file: UploadFile,
    current_user: CurrentUser,
) -> dict:
    """
    Preview first 5 rows of CSV/Excel file.
    Returns: { preview: [...], errors: [...] }
    """
    content = await file.read()
    filename = file.filename or "upload.csv"
    preview, errors = preview_products_file(content, filename, limit=5)
    return {"preview": preview, "errors": errors}


@router.post("/products/csv")
async def upload_products_csv(
    file: UploadFile,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """
    Upload CSV/Excel file with products.
    Columns: name, sku, price, url, category.
    Returns: { imported: N, errors: [{row: N, message: "..."}] }
    """
    content = await file.read()
    filename = file.filename or "upload.csv"

    products_data, errors = parse_products_file(content, filename, current_user.id)

    if errors and not products_data:
        return {"imported": 0, "errors": errors}

    imported = 0
    for data in products_data:
        product = Product(
            user_id=data["user_id"],
            name=data["name"],
            sku=data.get("sku"),
            current_price=data["current_price"],
            currency=data.get("currency", "RUB"),
            url=data.get("url"),
            category=data.get("category"),
        )
        db.add(product)
        imported += 1

    await db.flush()

    return {"imported": imported, "errors": errors}


@router.get("/products/template")
async def download_products_template(
    current_user: CurrentUser,
) -> PlainTextResponse:
    """Download CSV template for product import."""
    content = get_csv_template()
    return PlainTextResponse(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products_template.csv"},
    )
