"""Persist scrape_jobs pipeline metadata with reliable JSONB change tracking."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.app_tables import ScrapeJob
from app.modules.admin.parsing_admin import ParsingAdminService


class PipelineMetadataStore:
    """Read/write pipeline heartbeat and progress on a parent ScrapeJob."""

    def __init__(self, db: AsyncSession, job_id: UUID) -> None:
        self._db = db
        self._job_id = job_id

    @staticmethod
    def extract(config: Any) -> dict[str, Any]:
        """Return metadata dict from job.config."""
        if not isinstance(config, dict):
            return ParsingAdminService._build_initial_metadata()
        metadata = config.get("metadata")
        if isinstance(metadata, dict):
            return deepcopy(metadata)
        return ParsingAdminService._build_initial_metadata()

    async def load(self) -> tuple[ScrapeJob | None, dict[str, Any]]:
        job = await self._db.get(ScrapeJob, self._job_id)
        if job is None:
            return None, ParsingAdminService._build_initial_metadata()
        return job, self.extract(job.config)

    async def save(
        self,
        job: ScrapeJob,
        metadata: dict[str, Any],
        *,
        status: str | None = None,
    ) -> None:
        """Write metadata to job.config and commit."""
        if status is not None:
            job.status = status
        job.config = {"metadata": deepcopy(metadata)}
        flag_modified(job, "config")
        await self._db.commit()

    async def touch(
        self,
        job: ScrapeJob,
        metadata: dict[str, Any],
        *,
        stage: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update heartbeat fields and persist."""
        now_iso = datetime.now(UTC).isoformat()
        metadata["last_activity_at"] = now_iso
        if stage is not None:
            metadata["current_stage"] = stage
        if extra:
            metadata.update(extra)
        await self.save(job, metadata)
        return metadata

    @staticmethod
    def marketplace_codes_filter(metadata: dict[str, Any]) -> list[str] | None:
        """Optional subset of dim_marketplace.marketplace_code values for this run."""
        raw = metadata.get("marketplace_codes")
        if not isinstance(raw, list):
            return None
        codes = [str(item).strip() for item in raw if str(item).strip()]
        return codes or None
