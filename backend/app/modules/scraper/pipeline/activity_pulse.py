"""Heartbeat + metadata tail updates during long pipeline stages."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import sync_session_factory
from app.models.app_tables import ScrapeJob
from app.modules.admin.parsing_admin import ParsingAdminService
from app.modules.scraper.pipeline.metadata_store import PipelineMetadataStore
from app.modules.scraper.pipeline.worker_log_relay import (
    push_relay_line,
    should_pulse_db,
)

WORKER_LOG_TAIL_MAX = 20


def _append_tail(metadata: dict[str, Any], line: str) -> None:
    tail = metadata.get("worker_log_tail")
    if not isinstance(tail, list):
        tail = []
    else:
        tail = list(tail)
    tail.append(line)
    metadata["worker_log_tail"] = tail[-WORKER_LOG_TAIL_MAX:]


def pulse_job_activity_sync(
    job_id: UUID,
    line: str,
    *,
    stage: str = "scrape",
    force_db: bool = False,
) -> None:
    """Push a relay line and optionally refresh parent job heartbeat in Postgres."""
    push_relay_line(line, job_id=job_id)
    if not should_pulse_db(job_id, force=force_db):
        return

    db = sync_session_factory()
    try:
        job = db.get(ScrapeJob, job_id)
        if job is None:
            return
        metadata = PipelineMetadataStore.extract(job.config)
        metadata["last_activity_at"] = datetime.now(UTC).isoformat()
        metadata["current_stage"] = stage
        _append_tail(metadata, line)
        job.config = {"metadata": deepcopy(metadata)}
        flag_modified(job, "config")
        db.commit()
    finally:
        db.close()


async def pulse_job_activity_async(
    db: AsyncSession,
    job_id: UUID,
    line: str,
    *,
    stage: str = "discovery",
    force_db: bool = False,
) -> None:
    """Async heartbeat for discovery and orchestrator phases."""
    push_relay_line(line, job_id=job_id)
    if not should_pulse_db(job_id, force=force_db):
        return

    store = PipelineMetadataStore(db, job_id)
    job, metadata = await store.load()
    if job is None:
        return
    _append_tail(metadata, line)
    await store.touch(job, metadata, stage=stage)


async def discovery_activity_callback(
    db: AsyncSession,
    job_id: UUID,
    line: str,
) -> None:
    """Discovery crawl progress hook."""
    await pulse_job_activity_async(db, job_id, line, stage="discovery")
