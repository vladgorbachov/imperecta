"""Usage counters tied to the entitlements layer (plan limits)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entitlements import get_limit
from app.models.core import UserProduct


class UsageService:
    """Honest, source-of-truth usage counters per user.

    Returns ONLY counters that have a real source. Products are counted from
    `UserProduct` (active rows for the user). Competitor counts are
    intentionally omitted while no per-user competitor model exists - the
    project's `competitor` endpoints are still v2-migration stubs, so a
    `competitors.used` field would be fabricated data (Rule 3).
    """

    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def get_usage(self, plan: str) -> dict:
        products_used = await self.db.scalar(
            select(func.count())
            .select_from(UserProduct)
            .where(
                UserProduct.user_id == self.user_id,
                UserProduct.is_active.is_(True),
            ),
        )
        return {
            "products": {
                "used": int(products_used or 0),
                "limit": get_limit(plan, "products"),
            },
        }
