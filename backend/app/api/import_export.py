"""Import/Export API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.models import Product
from app.services.import_service import (
    get_csv_template,
    parse_products_file,
    preview_products_file,
)
from app.services.plan_limits import get_product_limit, is_free_plan

router = APIRouter()


class AutoCategorizeRequest(BaseModel):
    """Request body for auto-categorize."""

    products: list[dict] = Field(
        ...,
        description="List of {name, sku, price}",
    )


@router.post("/auto-categorize")
async def post_auto_categorize(
    body: AutoCategorizeRequest,
    current_user: CurrentUser,
) -> list[dict]:
    """AI auto-categorization for imported products. Returns list with suggested_category."""
    import logging

    from app.services.product_ai_service import auto_categorize

    logger = logging.getLogger(__name__)
    try:
        return await auto_categorize(body.products)
    except Exception as e:
        logger.warning("auto_categorize failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail="AI categorization service temporarily unavailable",
        )


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

    if is_free_plan(current_user.plan):
        limit = get_product_limit(current_user.plan)
        count_result = await db.execute(
            select(func.count()).select_from(Product).where(Product.user_id == current_user.id)
        )
        current_count = count_result.scalar() or 0
        slots = max(0, limit - current_count)
        if slots == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Product limit reached. Free plan allows up to {limit} products. Upgrade to add more.",
            )
        original_count = len(products_data)
        products_data = products_data[:slots]
        if original_count > slots:
            errors.insert(
                0,
                {"row": 0, "message": f"Only {slots} of {original_count} products imported. Free plan limit: {limit}."},
            )

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
