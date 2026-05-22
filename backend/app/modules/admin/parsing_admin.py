"""Parsing admin service contracts for scraper administration page."""

# Local runtime checks are intentionally not trusted for this module:
# database is hosted on Supabase and environment/runtime orchestration lives on Railway.

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import ScrapeJob, ScrapeLog
from app.models.dimensions import DimMarketplace


class ParsingAdminService:
    """
    Service layer for scraper administration (backend foundation).

    Recommended ScrapeJob.config["metadata"] JSONB shape:
    {
      "timings": {
        "discovery_ms": <int>,
        "scrape_ms": <int>,
        "persist_ms": <int>,
        "total_ms": <int>
      },
      "summary": {
        "listings_created": <int>,
        "prices_saved": <int>,
        "errors_count": <int>
      },
      "per_marketplace": [
        {
          "marketplace_id": "<uuid>",
          "domain": "<str>",
          "listings_created": <int>,
          "prices_saved": <int>,
          "errors_count": <int>,
          "duration_ms": <int>,
          "status": "completed|failed|running"
        }
      ]
    }

    Breakdown extension guideline:
    - Keep "timings", "summary", "per_marketplace" backward-compatible for frontend polling.
    - Add new fields under nested keys (for example per_marketplace[].extra) instead of
      replacing existing keys used by current UI cards.
    """

    TEST_PIPELINE_JOB_TYPE = "full_pipeline_test"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_test_marketplaces(self) -> list[dict[str, Any]]:
        """
        Return test marketplaces in frontend contract shape.

        Response item keys:
        - name
        - url
        - products_in_pool
        - last_successful_scrape
        - success_rate
        - last_run
        - status
        """
        log_stats_sq = (
            select(
                ScrapeLog.marketplace_id.label("marketplace_id"),
                func.count(ScrapeLog.id).label("total_runs"),
                func.sum(case((ScrapeLog.status == "success", 1), else_=0)).label("success_runs"),
                func.max(ScrapeLog.created_at).label("last_run"),
                func.max(
                    case(
                        (ScrapeLog.status == "success", ScrapeLog.created_at),
                        else_=None,
                    )
                ).label("last_successful_scrape"),
            )
            .group_by(ScrapeLog.marketplace_id)
            .subquery()
        )
        ranked_jobs_sq = (
            select(
                ScrapeJob.marketplace_id.label("marketplace_id"),
                ScrapeJob.status.label("job_status"),
                func.row_number()
                .over(
                    partition_by=ScrapeJob.marketplace_id,
                    order_by=ScrapeJob.created_at.desc(),
                )
                .label("rank_idx"),
            )
            .where(ScrapeJob.marketplace_id.is_not(None))
            .subquery()
        )
        latest_job_sq = (
            select(
                ranked_jobs_sq.c.marketplace_id,
                ranked_jobs_sq.c.job_status,
            )
            .where(ranked_jobs_sq.c.rank_idx == 1)
            .subquery()
        )

        stmt = (
            select(
                DimMarketplace.id,
                DimMarketplace.name,
                DimMarketplace.base_url,
                DimMarketplace.products_in_pool,
                DimMarketplace.last_scrape_status,
                log_stats_sq.c.total_runs,
                log_stats_sq.c.success_runs,
                log_stats_sq.c.last_run,
                log_stats_sq.c.last_successful_scrape,
                latest_job_sq.c.job_status,
            )
            .where(DimMarketplace.is_active.is_(True))
            .outerjoin(log_stats_sq, log_stats_sq.c.marketplace_id == DimMarketplace.id)
            .outerjoin(latest_job_sq, latest_job_sq.c.marketplace_id == DimMarketplace.id)
            .order_by(DimMarketplace.name.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.mappings().all()

        out: list[dict[str, Any]] = []
        for row in rows:
            total_runs = int(row["total_runs"] or 0)
            success_runs = int(row["success_runs"] or 0)
            success_rate = float((success_runs / total_runs) * 100) if total_runs > 0 else 0.0
            out.append(
                {
                    "name": row["name"],
                    "url": row["base_url"],
                    "products_in_pool": int(row["products_in_pool"] or 0),
                    "last_successful_scrape": self._to_iso(row["last_successful_scrape"]),
                    "success_rate": round(success_rate, 2),
                    "last_run": self._to_iso(row["last_run"]),
                    "status": self._normalize_marketplace_status(
                        latest_job_status=row["job_status"],
                        last_scrape_status=row["last_scrape_status"],
                    ),
                }
            )
        return out

    async def trigger_full_pipeline_test(self) -> dict[str, Any]:
        """
        Create a parent scrape job for full pipeline checks.

        Returns:
        {
          "job_id": "<uuid>",
          "started_at": "<iso_datetime>"
        }
        """
        started_at = datetime.now(UTC)
        metadata = self._build_initial_metadata()
        job = ScrapeJob(
            job_type=self.TEST_PIPELINE_JOB_TYPE,
            status="running",
            started_at=started_at,
            config={"metadata": metadata},
        )
        self.db.add(job)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            if await self._repair_scrape_job_type_constraint():
                self.db.add(job)
                await self.db.commit()
            else:
                raise ValueError(
                    "scrape_jobs.job_type does not allow 'full_pipeline_test' "
                    "and automatic constraint repair failed."
                ) from exc
        await self.db.refresh(job)
        return {
            "job_id": str(job.id),
            "started_at": self._to_iso(started_at),
        }

    async def get_test_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Return latest full pipeline runs.

        Response item keys:
        - job_id
        - started_at
        - completed_at
        - duration_seconds
        - listings_created
        - prices_saved
        - errors_count
        - status
        """
        safe_limit = max(1, min(limit, 200))
        result = await self.db.execute(
            select(ScrapeJob)
            .where(ScrapeJob.job_type == self.TEST_PIPELINE_JOB_TYPE)
            .order_by(ScrapeJob.created_at.desc())
            .limit(safe_limit)
        )
        jobs = result.scalars().all()

        out: list[dict[str, Any]] = []
        for job in jobs:
            metadata = self._extract_metadata(job.config)
            summary = metadata.get("summary", {}) if isinstance(metadata, dict) else {}
            out.append(
                {
                    "job_id": str(job.id),
                    "started_at": self._to_iso(job.started_at),
                    "completed_at": self._to_iso(job.completed_at),
                    "duration_seconds": self._duration_seconds(job.started_at, job.completed_at, job.duration_ms),
                    "listings_created": int(summary.get("listings_created", job.total_listings or 0)),
                    "prices_saved": int(summary.get("prices_saved", job.successful or 0)),
                    "errors_count": int(summary.get("errors_count", job.failed or 0)),
                    "status": self._normalize_job_status(job.status),
                }
            )
        return out

    async def get_job_status(self, job_id: UUID) -> dict[str, Any]:
        """
        Return pollable status payload for full pipeline test job.

        Output keys:
        - job_id
        - status ("running" | "completed" | "failed")
        - started_at
        - completed_at
        - duration_seconds
        - metadata (provided when status is completed/failed)
        """
        job = await self.db.get(ScrapeJob, job_id)
        if job is None:
            raise ValueError(f"Scrape job not found: {job_id}")

        normalized = self._normalize_job_status(job.status)
        completed = normalized in {"completed", "failed"}
        return {
            "job_id": str(job.id),
            "status": normalized,
            "current_stage": self._current_stage(self._extract_metadata(job.config)),
            "started_at": self._to_iso(job.started_at),
            "completed_at": self._to_iso(job.completed_at),
            "duration_seconds": self._duration_seconds(job.started_at, job.completed_at, job.duration_ms),
            "metadata": self._extract_metadata(job.config) if completed else None,
        }

    @staticmethod
    def _to_iso(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).isoformat()

    @staticmethod
    def _duration_seconds(
        started_at: datetime | None,
        completed_at: datetime | None,
        duration_ms: int | None,
    ) -> float | None:
        if duration_ms is not None and duration_ms >= 0:
            return round(duration_ms / 1000, 3)
        if started_at is not None and completed_at is not None:
            delta = completed_at - started_at
            return round(delta.total_seconds(), 3)
        return None

    @staticmethod
    def _normalize_job_status(raw_status: str | None) -> str:
        if raw_status in {"running", "completed", "failed"}:
            return raw_status
        if raw_status in {"pending"}:
            return "running"
        return "failed"

    @staticmethod
    def _normalize_marketplace_status(
        latest_job_status: str | None,
        last_scrape_status: str | None,
    ) -> str:
        if latest_job_status in {"running", "completed", "failed"}:
            return latest_job_status
        if latest_job_status == "pending":
            return "running"
        normalized = (last_scrape_status or "").strip().lower()
        if normalized in {"success", "completed", "ok"}:
            return "completed"
        if normalized in {"failed", "error", "timeout", "blocked"}:
            return "failed"
        return "running"

    @staticmethod
    def _build_initial_metadata() -> dict[str, Any]:
        return {
            "current_stage": "queued",
            "timings": {
                "discovery_ms": 0,
                "scrape_ms": 0,
                "persist_ms": 0,
                "total_ms": 0,
            },
            "summary": {
                "listings_created": 0,
                "prices_saved": 0,
                "errors_count": 0,
            },
            "per_marketplace": [],
        }

    @staticmethod
    def _extract_metadata(config: Any) -> dict[str, Any]:
        if not isinstance(config, dict):
            return {}
        metadata = config.get("metadata")
        if isinstance(metadata, dict):
            return metadata
        return config

    @staticmethod
    def _current_stage(metadata: dict[str, Any]) -> str | None:
        stage = metadata.get("current_stage")
        if isinstance(stage, str) and stage.strip():
            return stage
        return None

    async def _repair_scrape_job_type_constraint(self) -> bool:
        """Allow full_pipeline_test in scrape_jobs.job_type CHECK constraint."""
        try:
            await self.db.execute(
                text("ALTER TABLE scrape_jobs DROP CONSTRAINT IF EXISTS ck_scrape_jobs_job_type")
            )
            await self.db.execute(
                text(
                    "ALTER TABLE scrape_jobs "
                    "ADD CONSTRAINT ck_scrape_jobs_job_type "
                    "CHECK (job_type IN ('scheduled','manual','retry','backfill','discovery','full_pipeline_test'))"
                )
            )
            await self.db.commit()
            return True
        except Exception:
            await self.db.rollback()
            return False

