"""Entitlements API: live usage counters against plan limits."""

from fastapi import APIRouter

from app.common.deps import CurrentUser, DbSession
from app.modules.entitlements.service import UsageService

router = APIRouter(prefix="/entitlements", tags=["entitlements"])


@router.get("/usage")
async def get_usage(current_user: CurrentUser, db: DbSession) -> dict:
    """Return per-user usage vs plan limits.

    Response shape today:
        {"products": {"used": int, "limit": int}}

    `competitors` is intentionally absent until a per-user competitor model
    exists; surfacing a hardcoded zero would be fabricated data.
    """
    service = UsageService(db, current_user.id)
    return await service.get_usage(current_user.plan)
