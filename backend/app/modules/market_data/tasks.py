"""Market data ingestion Celery tasks. Isolated from legacy dashboard/anomalies."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.modules.market_data.aggregation import MarketDataAggregateService
from app.modules.market_data.ingestion import MarketDataIngestionService
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


async def _run_full_pipeline(include_commodities: bool = False) -> dict[str, int]:
    settings = Settings()
    engine = create_async_engine(
        str(settings.database_url),
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    try:
        async with async_session() as db:
            try:
                ingest_svc = MarketDataIngestionService(db)
                ingest_results = await ingest_svc.ingest_all(include_commodities=include_commodities)

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
    finally:
        await engine.dispose()


@celery_app.task(name="ingest_market_data", bind=True)
def ingest_market_data(self):
    """
    Full 2-hour pipeline: forex, crypto, fuel ingestion (no commodities).
    Commodities run separately 4x/day via ingest_commodities.
    """
    try:
        results = _run_async(_run_full_pipeline(include_commodities=False))
        logger.info("Market data pipeline completed: %s", results)
        return results
    except Exception as error:
        logger.exception("Market data pipeline failed: %s", error)
        raise


async def _run_commodities_only_pipeline() -> int:
    """Run only commodities ingestion and aggregation."""
    settings = Settings()
    engine = create_async_engine(
        str(settings.database_url),
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    try:
        async with async_session() as db:
            try:
                ingest_svc = MarketDataIngestionService(db)
                count = await ingest_svc.ingest_commodities_only()
                agg_svc = MarketDataAggregateService(db)
                await agg_svc.materialize_all()
                await db.commit()
                logger.info("Commodities pipeline committed: %d items", count)
                return count
            except Exception:
                await db.rollback()
                raise
    finally:
        await engine.dispose()


@celery_app.task(name="ingest_commodities", bind=True)
def ingest_commodities(self):
    """
    Commodities only: 4x/day (0, 6, 12, 18 UTC).
    6 symbols: XAU, XAG, XPT, XPD (GoldAPI) + WTI, BRENT (Alpha Vantage).
    """
    try:
        count = _run_async(_run_commodities_only_pipeline())
        logger.info("Commodities ingestion completed: %d items", count)
        return count
    except Exception as error:
        logger.exception("Commodities ingestion failed: %s", error)
        raise
