"""Orchestrates admin full pipeline test (discovery → scrape → finalize)."""

from __future__ import annotations

import time
import traceback
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.app_tables import ScrapeJob
from app.modules.scraper.pipeline.discovery_phase import run_discovery_phase
from app.modules.scraper.pipeline.metadata_store import PipelineMetadataStore
from app.modules.scraper.tasks import (
    _finalize_full_pipeline_job,
    _run_scrape_all_pool,
)

slog = structlog.get_logger(__name__)


class FullPipelineTestRunner:
    """Run a single full_pipeline_test parent job end-to-end."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        celery_task_id: str,
    ) -> None:
        self._session_factory = session_factory
        self._celery_task_id = celery_task_id

    async def run(self, parent_job_id: UUID) -> dict[str, Any]:
        discovery_ms = 0
        scrape_ms = 0
        persist_ms = 0
        hard_error: str | None = None
        per_marketplace_seed: dict[UUID, dict[str, Any]] = {}

        try:
            async with self._session_factory() as db:
                store = PipelineMetadataStore(db, parent_job_id)
                job, metadata = await store.load()
                if job is None:
                    return {"status": "not_found", "job_id": str(parent_job_id)}

                metadata["celery_task_id"] = self._celery_task_id
                marketplace_codes = PipelineMetadataStore.marketplace_codes_filter(metadata)
                await store.touch(job, metadata, stage="discovery", extra={"celery_task_id": self._celery_task_id})

                discovery_started = time.perf_counter()
                per_marketplace_seed, discovery_errors = await run_discovery_phase(
                    db,
                    parent_job_id=parent_job_id,
                    marketplace_codes=marketplace_codes,
                )
                discovery_ms = int((time.perf_counter() - discovery_started) * 1000)

                job, metadata = await store.load()
                if job is None:
                    return {"status": "not_found", "job_id": str(parent_job_id)}
                metadata["discovery_errors"] = discovery_errors[:20]
                if discovery_errors and "pipeline_job_cancelled" in discovery_errors:
                    hard_error = "pipeline_job_cancelled"
                await store.touch(job, metadata, stage="scrape")

            if hard_error == "pipeline_job_cancelled":
                async with self._session_factory() as db:
                    job = await db.get(ScrapeJob, parent_job_id)
                    if job is not None:
                        metadata = await _finalize_full_pipeline_job(
                            db,
                            job,
                            discovery_ms=discovery_ms,
                            scrape_ms=0,
                            persist_ms=0,
                            per_marketplace_seed=per_marketplace_seed,
                            hard_error=hard_error,
                        )
                        return {
                            "job_id": str(job.id),
                            "status": job.status,
                            "summary": metadata.get("summary", {}),
                        }
                return {"job_id": str(parent_job_id), "status": "failed", "error": hard_error}

            scrape_started = time.perf_counter()
            scrape_result = _run_scrape_all_pool(scrape_job_id=parent_job_id)
            scrape_ms = int((time.perf_counter() - scrape_started) * 1000)
            if scrape_result.get("error"):
                hard_error = str(scrape_result["error"])

            async with self._session_factory() as db:
                store = PipelineMetadataStore(db, parent_job_id)
                job, metadata = await store.load()
                if job is None:
                    return {"status": "not_found", "job_id": str(parent_job_id)}
                await store.touch(job, metadata, stage="persist")

                job = await db.get(ScrapeJob, parent_job_id)
                if job is None:
                    return {"status": "not_found", "job_id": str(parent_job_id)}
                metadata = await _finalize_full_pipeline_job(
                    db,
                    job,
                    discovery_ms=discovery_ms,
                    scrape_ms=scrape_ms,
                    persist_ms=0,
                    per_marketplace_seed=per_marketplace_seed,
                    hard_error=hard_error,
                )
                return {
                    "job_id": str(job.id),
                    "status": job.status,
                    "summary": metadata.get("summary", {}),
                }
        except Exception:
            tb = traceback.format_exc()
            hard_error = tb
            slog.exception("run_full_pipeline_test_failed", parent_job_id=str(parent_job_id))
            try:
                async with self._session_factory() as db:
                    job = await db.get(ScrapeJob, parent_job_id)
                    if job is not None:
                        await _finalize_full_pipeline_job(
                            db,
                            job,
                            discovery_ms=discovery_ms,
                            scrape_ms=scrape_ms,
                            persist_ms=persist_ms,
                            per_marketplace_seed=per_marketplace_seed,
                            hard_error=hard_error,
                        )
            except Exception:
                slog.exception(
                    "run_full_pipeline_test_mark_failed_error",
                    parent_job_id=str(parent_job_id),
                )
            return {
                "job_id": str(parent_job_id),
                "status": "failed",
                "error": "pipeline_execution_failed",
            }
