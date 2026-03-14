"""Data retention cleanup tasks."""

import logging
from datetime import datetime, timedelta, timezone

from app.database import sync_session_factory
from app.models import AIChatMessage, ApiLog, PriceSnapshot, ScrapeLog
from app.models.alert_event import AlertEvent
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="cleanup_old_data")
def cleanup_old_data():
    """Delete price snapshots and scrape logs older than 30 days, api_logs older than 60 days."""

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    cutoff_60 = datetime.now(timezone.utc) - timedelta(days=60)
    cutoff_chat = datetime.now(timezone.utc) - timedelta(days=365)
    cutoff_alerts = datetime.now(timezone.utc) - timedelta(days=180)

    with sync_session_factory() as db:
        deleted_snapshots = (
            db.query(PriceSnapshot).filter(PriceSnapshot.scraped_at < cutoff).delete(synchronize_session=False)
        )
        deleted_logs = (
            db.query(ScrapeLog).filter(ScrapeLog.created_at < cutoff).delete(synchronize_session=False)
        )
        deleted_api_logs = (
            db.query(ApiLog).filter(ApiLog.created_at < cutoff_60).delete(synchronize_session=False)
        )
        deleted_chat = (
            db.query(AIChatMessage).filter(AIChatMessage.created_at < cutoff_chat).delete(synchronize_session=False)
        )
        deleted_alerts = (
            db.query(AlertEvent).filter(AlertEvent.triggered_at < cutoff_alerts).delete(synchronize_session=False)
        )
        db.commit()

    logger.info(
        "Cleanup: %d snapshots, %d scrape_logs, %d api_logs, %d ai_chat_messages, %d alert_events deleted",
        deleted_snapshots,
        deleted_logs,
        deleted_api_logs,
        deleted_chat,
        deleted_alerts,
    )
    return {
        "deleted_snapshots": deleted_snapshots,
        "deleted_scrape_logs": deleted_logs,
        "deleted_api_logs": deleted_api_logs,
        "deleted_ai_chat_messages": deleted_chat,
        "deleted_alert_events": deleted_alerts,
    }
