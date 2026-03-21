"""Market data aggregation (v2 migration stub)."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
_V2_MSG = "Pending migration to v2 schema"


class MarketDataAggregateService:
    """Placeholder for materialized market aggregates."""

    def __init__(self, db: "AsyncSession"):
        self.db = db

    async def materialize_all(self) -> dict[str, int]:
        logger.warning("MarketDataAggregateService.materialize_all skipped: %s", _V2_MSG)
        return {"aggregate_skipped": 0}
