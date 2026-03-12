"""Market data ingestion Celery tasks. Isolated from legacy dashboard/anomalies."""

import asyncio
import logging

from app.database import async_session_maker
from app.services.market_data.aggregate_service import MarketDataAggregateService
from app.services.market_data.ingestion_service import MarketDataIngestionService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine from sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _run_full_pipeline() -> dict[str, int]:
    """Run ingestion then aggregate materialization."""
    async with async_session_maker() as db:
        try:
            ingest_svc = MarketDataIngestionService(db)
            ingest_results = await ingest_svc.ingest_all()

            agg_svc = MarketDataAggregateService(db)
            agg_results = await agg_svc.materialize_all()

            await db.commit()
            logger.info(
                "Market data pipeline committed: ingest=%s aggregate=%s",
                ingest_results,
                agg_results,
            )
            return {**ingest_results, **agg_results}
        except Exception:
            await db.rollback()
            raise


@celery_app.task(name="ingest_market_data", bind=True)
def ingest_market_data(self):
    """
    Full 2-hour pipeline: forex, crypto, commodities, fuel ingestion;
    then ticker and overview aggregate materialization.
    Persists to markets_* tables. Serves stored results via API.
    """
    try:
        results = _run_async(_run_full_pipeline())
        logger.info("Market data pipeline completed: %s", results)
        return results
    except Exception as e:
        logger.exception("Market data pipeline failed: %s", e)
        raise
