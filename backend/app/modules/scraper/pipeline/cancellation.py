"""Pipeline job cancellation checks for long-running Celery tasks."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import ScrapeJob
from app.modules.admin.parsing_admin import ParsingAdminService

slog = structlog.get_logger(__name__)


async def is_pipeline_job_cancelled(db: AsyncSession, job_id: UUID) -> bool:
    """Return True when parent full_pipeline_test job is no longer running."""
    job = await db.get(ScrapeJob, job_id)
    if job is None:
        return True
    if job.job_type != ParsingAdminService.TEST_PIPELINE_JOB_TYPE:
        return False
    normalized = ParsingAdminService._normalize_job_status(job.status)
    return normalized != "running"


def revoke_celery_task(celery_task_id: str | None) -> None:
    """Best-effort terminate of a pipeline Celery task."""
    if not celery_task_id or not str(celery_task_id).strip():
        return
    try:
        from app.workers.celery_app import celery_app

        celery_app.control.revoke(str(celery_task_id), terminate=True, signal="SIGTERM")
        slog.info("pipeline_celery_task_revoked", celery_task_id=celery_task_id)
    except Exception as exc:
        slog.warning(
            "pipeline_celery_revoke_failed",
            celery_task_id=celery_task_id,
            error=str(exc),
        )
