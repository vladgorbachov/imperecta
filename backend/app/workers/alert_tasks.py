"""Alert trigger tasks: periodic evaluation of user alert rules."""

from __future__ import annotations

import asyncio

import structlog

from app.database import async_session_maker
from app.modules.alerts.engine import evaluate_alert_rules
from app.observability.sentry_init import capture_exception_if_initialized
from app.workers.celery_app import celery_app

slog = structlog.get_logger(__name__)


async def _run_evaluation() -> dict[str, int]:
    async with async_session_maker() as db:
        return await evaluate_alert_rules(db)


@celery_app.task(name="evaluate_price_alerts")
def evaluate_price_alerts() -> dict[str, int]:
    """Run the alert trigger engine once (reads ORM, writes via ALERT door)."""
    try:
        summary = asyncio.run(_run_evaluation())
        if summary.get("fired"):
            slog.info("alert_rules_fired", **summary)
        return summary
    except Exception as exc:
        slog.error("alert_evaluation_failed", error=str(exc)[:500])
        capture_exception_if_initialized(exc)
        return {}
