"""Maintenance tasks: service-data retention (DDL moved to pg_cron)."""

from __future__ import annotations

import structlog

from app.modules.persist.retention import run_retention_pass
from app.observability.sentry_init import capture_exception_if_initialized
from app.workers.celery_app import celery_app

slog = structlog.get_logger(__name__)


@celery_app.task(name="run_service_data_retention")
def run_service_data_retention() -> dict[str, int]:
    """Delete service-data rows via the gate (per-table windows, fail-open)."""
    try:
        return run_retention_pass()
    except Exception as exc:
        slog.error("retention_pass_failed", error=str(exc)[:500])
        capture_exception_if_initialized(exc)
        return {}
