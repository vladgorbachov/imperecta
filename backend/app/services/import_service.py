"""CSV/Excel import: creates DimProduct + UserProduct rows."""

import logging
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import UserProduct
from app.models.dimensions import DimProduct
from app.modules.user_products.service import parse_products_file

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    s = (name or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s[:500]


class ImportService:
    """Persist imported product rows as canonical dim_product + user_products."""

    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def import_from_file(self, content: bytes, filename: str) -> dict:
        """
        Parse file and insert DimProduct + UserProduct for each valid row.

        Returns counts and per-row errors (same shape as API expects).
        """
        rows, errors = parse_products_file(content, filename, self.user_id)
        imported = 0
        for row in rows:
            try:
                name = row["name"]
                nm = _normalize_name(name)
                product = DimProduct(
                    name=name[:500],
                    name_normalized=nm or "product",
                    sku_universal=row.get("sku"),
                    is_active=True,
                )
                self.db.add(product)
                await self.db.flush()

                up = UserProduct(
                    user_id=self.user_id,
                    product_id=product.id,
                    custom_sku=row.get("sku"),
                    target_price=row["current_price"],
                    currency_code=str(row.get("currency") or "EUR")[:3],
                    is_active=True,
                )
                self.db.add(up)
                imported += 1
            except Exception as exc:
                logger.exception("import row failed: %s", exc)
                errors.append({"row": 0, "message": str(exc)})

        try:
            await self.db.commit()
        except Exception as exc:
            logger.error("import commit failed: %s", exc)
            await self.db.rollback()
            return {"imported": 0, "errors": errors + [{"row": 0, "message": str(exc)}]}

        return {"imported": imported, "errors": errors}
