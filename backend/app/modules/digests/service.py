"""Digest business logic (v2 migration stub)."""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import Digest
from app.models.core import User

logger = logging.getLogger(__name__)
_V2_MSG = "Pending migration to v2 schema"


async def collect_period_data(session: AsyncSession, user_id: UUID, period_start: datetime, period_end: datetime) -> dict:
    _ = session, user_id, period_start, period_end
    logger.warning("collect_period_data: %s", _V2_MSG)
    return {"top_changes": [], "promos": [], "anomalies": [], "summary_stats": {}}


async def send_digest_for_user(session: AsyncSession, user: User, content_md: str, period: str) -> None:
    _ = session, user, content_md, period
    logger.warning("send_digest_for_user: %s", _V2_MSG)


async def generate_and_store_digest(
    session: AsyncSession,
    user: User,
    period_type: str,
    period_start: datetime,
    period_end: datetime,
) -> Digest:
    digest = Digest(
        user_id=user.id,
        period_type=period_type,
        digest_type="market_overview",
        period_start=period_start,
        period_end=period_end,
        content_md="",
        summary_json={"message": _V2_MSG, "markdown": ""},
    )
    session.add(digest)
    await session.flush()
    return digest
