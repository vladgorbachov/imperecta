"""Celery task wrappers for market_data ingestion (Tier-2).

Tier-2 (workers) owns Celery; Tier-1 (market_data) does not. These two wrappers
only manage a sync DB session for persist and an async fetch bridge into the
module's Tier-1 contract (`IngestionService`); the task NAMES match the prior
Tier-1 definitions verbatim so beat schedules and `/markets/ingest` remain compatible.
"""

import asyncio
import logging

from app.database import sync_session_factory
from app.models.facts import (
    FactCommodityPrice,
    FactCryptoPrice,
    FactCurrencyRate,
    FactFuelPrice,
)
from app.modules.market_data.ingestion import IngestionService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

FACT_TABLE_NAMES = (
    FactCurrencyRate.__tablename__,
    FactCryptoPrice.__tablename__,
    FactCommodityPrice.__tablename__,
    FactFuelPrice.__tablename__,
)


def _run_async(coro):
    """Run async coroutine from sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


@celery_app.task(name="ingest_market_data", bind=True)
def ingest_market_data(self):
    async def _do() -> dict:
        db = sync_session_factory()
        try:
            svc = IngestionService(db)
            return await svc.ingest_all(include_commodities=True)
        finally:
            db.close()

    try:
        result = _run_async(_do())
        return {"status": "ok", "counts": result, "fact_tables": list(FACT_TABLE_NAMES)}
    except Exception as exc:
        logger.exception("ingest_market_data failed: %s", exc)
        return {"status": "error", "message": str(exc)}


@celery_app.task(name="ingest_commodities", bind=True)
def ingest_commodities(self):
    async def _do() -> int:
        db = sync_session_factory()
        try:
            svc = IngestionService(db)
            return await svc.ingest_commodities_only()
        finally:
            db.close()

    try:
        n = _run_async(_do())
        return {"status": "ok", "commodities": n, "fact_tables": list(FACT_TABLE_NAMES)}
    except Exception as exc:
        logger.exception("ingest_commodities failed: %s", exc)
        return {"status": "error", "message": str(exc)}
