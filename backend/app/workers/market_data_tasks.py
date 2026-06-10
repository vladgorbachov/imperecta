"""Celery task wrappers for market_data ingestion (Tier-2).

Tier-2 (workers) owns Celery; Tier-1 (market_data) does not. These two wrappers
only manage an async engine + session and dispatch to the module's Tier-1
contract (`IngestionService`); the task NAMES match the prior Tier-1
definitions verbatim so beat schedules and `/markets/ingest` remain compatible.
"""

# TODO(workers): extract a shared async-session helper for Tier-2 task wrappers
# (duplicated with app.modules.scraper.tasks). Not done in M3b to keep the pass
# scope-limited; planned alongside the broader worker-tier refactor.

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
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


def _make_session_factory():
    settings = Settings()
    engine = create_async_engine(
        str(settings.database_url),
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    return engine, factory


@celery_app.task(name="ingest_market_data", bind=True)
def ingest_market_data(self):
    async def _do() -> dict:
        engine, session_factory = _make_session_factory()
        try:
            async with session_factory() as db:
                svc = IngestionService(db)
                return await svc.ingest_all(include_commodities=True)
        finally:
            await engine.dispose()

    try:
        result = _run_async(_do())
        return {"status": "ok", "counts": result, "fact_tables": list(FACT_TABLE_NAMES)}
    except Exception as exc:
        logger.exception("ingest_market_data failed: %s", exc)
        return {"status": "error", "message": str(exc)}


@celery_app.task(name="ingest_commodities", bind=True)
def ingest_commodities(self):
    async def _do() -> int:
        engine, session_factory = _make_session_factory()
        try:
            async with session_factory() as db:
                svc = IngestionService(db)
                return await svc.ingest_commodities_only()
        finally:
            await engine.dispose()

    try:
        n = _run_async(_do())
        return {"status": "ok", "commodities": n, "fact_tables": list(FACT_TABLE_NAMES)}
    except Exception as exc:
        logger.exception("ingest_commodities failed: %s", exc)
        return {"status": "error", "message": str(exc)}
