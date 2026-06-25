"""Heartbeat + metadata tail updates during long pipeline stages."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import sync_session_factory
from app.models.app_tables import ScrapeJob
from app.modules.persist.meta_write import build_scrape_job_fields, write_meta_sync
from app.modules.scraper.pipeline.metadata_store import PipelineMetadataStore
from app.modules.scraper.pipeline.worker_log_relay import (
    push_relay_line,
    should_pulse_db,
)

slog = structlog.get_logger(__name__)

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

    try:
        db = sync_session_factory()
        try:
            job = db.get(ScrapeJob, job_id)
            if job is None:
                return
            metadata = PipelineMetadataStore.extract(job.config)
        finally:
            db.close()
        metadata["last_activity_at"] = datetime.now(UTC).isoformat()
        metadata["current_stage"] = stage
        _append_tail(metadata, line)
        write_meta_sync(
            table="scrape_jobs",
            operation="update",
            fields=build_scrape_job_fields(
                id=job_id,
                config={"metadata": deepcopy(metadata)},
            ),
            reject_source="activity_pulse",
        )
    except Exception:
        slog.exception("job_activity_pulse_failed", job_id=str(job_id))


def pulse_parent_heartbeat_sync(
    parent_job_id: UUID,
    *,
    force: bool = False,
) -> None:
    """Refresh parent pipeline heartbeat under a distinct throttle key.

    Called from long-running scrape children so the parent survives reaper
    checks even when orchestrator_tick cannot run. Failures are logged and
    swallowed — a heartbeat must never abort scraping.
    """
    if not should_pulse_db(parent_job_id, force=force):
        return

    try:
        db = sync_session_factory()
        try:
            job = db.get(ScrapeJob, parent_job_id)
            if job is None:
                return
            metadata = PipelineMetadataStore.extract(job.config)
        finally:
            db.close()
        metadata["last_activity_at"] = datetime.now(UTC).isoformat()
        write_meta_sync(
            table="scrape_jobs",
            operation="update",
            fields=build_scrape_job_fields(
                id=parent_job_id,
                config={"metadata": deepcopy(metadata)},
            ),
            reject_source="activity_pulse",
        )
    except Exception:
        slog.exception(
            "parent_heartbeat_pulse_failed",
            parent_job_id=str(parent_job_id),
        )


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
