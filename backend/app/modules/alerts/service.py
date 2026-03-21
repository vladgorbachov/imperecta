"""AI service for alert event explanations (v2 migration stub)."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
_V2_MSG = "Pending migration to v2 schema"


async def generate_alert_explanation(db: AsyncSession, alert_event_id: int) -> dict:
    _ = db, alert_event_id
    logger.warning("generate_alert_explanation: %s", _V2_MSG)
    return {"explanation": _V2_MSG, "recommendation": None, "recommended_price": None}


async def generate_auto_response(db: AsyncSession, alert_event_id: int) -> dict:
    _ = db, alert_event_id
    logger.warning("generate_auto_response: %s", _V2_MSG)
    return {"recommended_price": None, "reasoning": _V2_MSG, "expected_impact": ""}
