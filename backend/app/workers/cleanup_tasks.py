"""Data retention cleanup tasks."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.database import async_session_maker
from app.models import AIChatMessage, ApiLog, PriceSnapshot, ScrapeLog
from app.models.alert_event import AlertEvent
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


@celery_app.task(name="cleanup_old_data")
def cleanup_old_data() -> None:
    """Delete data older than retention period.

    Retention periods:
    - price_snapshots: 180 days
    - scrape_logs: 90 days
    - api_logs: 60 days
    - ai_chat_messages: 365 days
    - alert_events: 180 days
    """

    async def _do() -> None:
        now = datetime.now(timezone.utc)
        async with async_session_maker() as session:
            # price_snapshots older than 180 days
            cutoff_snapshots = now - timedelta(days=180)
            r1 = await session.execute(
                delete(PriceSnapshot).where(PriceSnapshot.scraped_at < cutoff_snapshots)
            )
            logger.info(f"Deleted {r1.rowcount} price_snapshots older than 180 days")

            # scrape_logs older than 90 days
            cutoff_scrape = now - timedelta(days=90)
            r2 = await session.execute(
                delete(ScrapeLog).where(ScrapeLog.created_at < cutoff_scrape)
            )
            logger.info(f"Deleted {r2.rowcount} scrape_logs older than 90 days")

            # api_logs older than 60 days
            cutoff_api = now - timedelta(days=60)
            r3 = await session.execute(
                delete(ApiLog).where(ApiLog.created_at < cutoff_api)
            )
            logger.info(f"Deleted {r3.rowcount} api_logs older than 60 days")

            # ai_chat_messages older than 365 days
            cutoff_chat = now - timedelta(days=365)
            r4 = await session.execute(
                delete(AIChatMessage).where(AIChatMessage.created_at < cutoff_chat)
            )
            logger.info(f"Deleted {r4.rowcount} ai_chat_messages older than 365 days")

            # alert_events older than 180 days
            cutoff_alerts = now - timedelta(days=180)
            r5 = await session.execute(
                delete(AlertEvent).where(AlertEvent.triggered_at < cutoff_alerts)
            )
            logger.info(f"Deleted {r5.rowcount} alert_events older than 180 days")

            await session.commit()

    _run_async(_do())
