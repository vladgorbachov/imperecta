"""Parsing admin service contracts for scraper administration page."""

# Local runtime checks are intentionally not trusted for this module:
# database is hosted on Supabase and environment/runtime orchestration lives on Railway.

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import ScrapeJob, ScrapeLog
from app.models.dimensions import DimCountry, DimMarketplace


@dataclass(frozen=True)
class TestMarketplaceSeed:
    """Static marketplace seed definition for scraper administration checks."""

    name: str
    domain: str
    country_code: str


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
    """

    TEST_PIPELINE_JOB_TYPE = "full_pipeline_test"
    TEST_MARKETPLACES: tuple[TestMarketplaceSeed, ...] = (
        TestMarketplaceSeed(name="Rozetka", domain="rozetka.com.ua", country_code="UA"),
        TestMarketplaceSeed(name="Bomba", domain="bomba.md", country_code="MD"),
        TestMarketplaceSeed(name="Pandashop", domain="pandashop.md", country_code="MD"),
        TestMarketplaceSeed(name="Musicshop", domain="musicshop.md", country_code="MD"),
        TestMarketplaceSeed(name="Comfy", domain="comfy.ua", country_code="UA"),
    )

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
        domains = [seed.domain for seed in self.TEST_MARKETPLACES]
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
            .where(DimMarketplace.domain.in_(domains))
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

    async def add_test_marketplaces(self) -> dict[str, Any]:
        """Ensure five predefined test marketplaces exist without duplicates."""
        domains = [seed.domain for seed in self.TEST_MARKETPLACES]
        existing_rows = await self.db.execute(
            select(DimMarketplace.domain).where(DimMarketplace.domain.in_(domains))
        )
        existing_domains = {domain for domain in existing_rows.scalars().all()}

        country_map = await self._load_country_currency_map()
        fallback_country_code, fallback_currency_code = await self._load_fallback_country_currency()

        added = 0
        skipped = 0
        created: list[dict[str, Any]] = []
        for seed in self.TEST_MARKETPLACES:
            if seed.domain in existing_domains:
                skipped += 1
                continue

            country_code, currency_code = country_map.get(
                seed.country_code,
                (fallback_country_code, fallback_currency_code),
            )
            code = self._make_marketplace_code(seed.domain)
            marketplace = DimMarketplace(
                marketplace_code=code,
                name=seed.name,
                source_type="marketplace",
                country_code=country_code,
                operates_in=[country_code],
                domain=seed.domain,
                base_url=f"https://{seed.domain}",
                api_available=False,
                currency_code=currency_code,
                scraper_type="web_api",
                is_active=True,
            )
            self.db.add(marketplace)
            added += 1
            created.append(
                {
                    "name": seed.name,
                    "domain": seed.domain,
                    "country_code": country_code,
                    "currency_code": currency_code,
                }
            )
            existing_domains.add(seed.domain)

        await self.db.commit()
        return {
            "added": added,
            "skipped": skipped,
            "total_requested": len(self.TEST_MARKETPLACES),
            "marketplaces": created,
        }

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
            raise ValueError(
                "scrape_jobs.job_type does not allow 'full_pipeline_test'. "
                "Run this SQL in Supabase SQL Editor first:\n"
                "ALTER TABLE scrape_jobs DROP CONSTRAINT IF EXISTS ck_scrape_jobs_job_type;\n"
                "ALTER TABLE scrape_jobs ADD CONSTRAINT ck_scrape_jobs_job_type "
                "CHECK (job_type IN ('scheduled','manual','retry','backfill','discovery','full_pipeline_test'));"
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

    async def _load_country_currency_map(self) -> dict[str, tuple[str, str]]:
        requested_codes = {seed.country_code for seed in self.TEST_MARKETPLACES}
        result = await self.db.execute(
            select(DimCountry.country_code, DimCountry.currency_code).where(
                DimCountry.country_code.in_(requested_codes)
            )
        )
        return {row.country_code: (row.country_code, row.currency_code) for row in result}

    async def _load_fallback_country_currency(self) -> tuple[str, str]:
        fallback = await self.db.execute(
            select(DimCountry.country_code, DimCountry.currency_code)
            .where(DimCountry.is_active.is_(True))
            .order_by(DimCountry.country_code.asc())
            .limit(1)
        )
        row = fallback.first()
        if row is None:
            raise ValueError("dim_country has no active rows; cannot seed test marketplaces")
        return row.country_code, row.currency_code

    @staticmethod
    def _make_marketplace_code(domain: str) -> str:
        normalized = re.sub(r"[^a-z0-9_]+", "_", domain.lower())
        code = normalized.replace(".", "_")
        if len(code) <= 50:
            return code
        digest = hashlib.sha256(domain.encode("utf-8")).hexdigest()[:10]
        return f"{code[:39]}_{digest}"[:50]
