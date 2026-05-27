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

from app.entitlements.plan import UserPlan
from app.models.app_tables import ScrapeJob, ScrapeLog
from app.models.core import User, UserProduct
from app.models.dimensions import DimMarketplace
from app.models.facts import FactListing
from app.modules.core.auth.service import hash_password
from app.modules.core.schemas import ALLOWED_LANGUAGE_CODES


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
    STALE_PIPELINE_TIMEOUT_MINUTES = 90

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
        await self._fail_stale_running_pipeline_jobs()
        active = await self.get_active_pipeline_job()
        if active is not None:
            raise ValueError(
                f"Pipeline job already running: {active['job_id']}. Wait until it finishes or fails."
            )

        started_at = datetime.now(UTC)
        metadata = self._build_initial_metadata()
        metadata["last_activity_at"] = self._to_iso(started_at)
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
        await self._fail_stale_running_pipeline_jobs()
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
        await self._fail_stale_running_pipeline_jobs()
        job = await self.db.get(ScrapeJob, job_id)
        if job is None:
            raise ValueError(f"Scrape job not found: {job_id}")

        metadata = self._extract_metadata(job.config)
        last_log_at = await self._job_last_log_at(job.id)
        metadata = self._merge_runtime_activity(
            job=job,
            metadata=metadata,
            last_log_at=last_log_at,
        )
        normalized = self._normalize_job_status(job.status)
        return {
            "job_id": str(job.id),
            "status": normalized,
            "current_stage": self._resolve_current_stage(metadata, normalized, last_log_at),
            "started_at": self._to_iso(job.started_at),
            "completed_at": self._to_iso(job.completed_at),
            "duration_seconds": self._duration_seconds(job.started_at, job.completed_at, job.duration_ms),
            "metadata": metadata,
        }

    async def get_users_detailed(self, limit: int = 500) -> list[dict[str, Any]]:
        """Detailed users list for admin diagnostics tab."""
        safe_limit = max(1, min(limit, 2000))
        stmt = (
            select(
                User.id,
                User.email,
                User.name,
                User.company_name,
                User.plan,
                User.is_active,
                User.is_superuser,
                User.language,
                User.timezone,
                User.login_count,
                User.last_login_at,
                User.created_at,
                func.count(UserProduct.id).label("tracked_products"),
            )
            .outerjoin(UserProduct, UserProduct.user_id == User.id)
            .group_by(User.id)
            .order_by(User.created_at.desc())
            .limit(safe_limit)
        )
        result = await self.db.execute(stmt)
        rows = result.mappings().all()
        return [
            {
                "id": str(row["id"]),
                "email": row["email"],
                "name": row["name"],
                "company_name": row["company_name"],
                "plan": row["plan"],
                "is_active": bool(row["is_active"]),
                "is_superuser": bool(row["is_superuser"]),
                "language": row["language"],
                "timezone": row["timezone"],
                "login_count": int(row["login_count"] or 0),
                "tracked_products": int(row["tracked_products"] or 0),
                "last_login_at": self._to_iso(row["last_login_at"]),
                "created_at": self._to_iso(row["created_at"]),
            }
            for row in rows
        ]

    async def create_user(
        self,
        *,
        email: str,
        password: str,
        name: str | None,
        company_name: str | None,
        plan: str,
        language: str,
        timezone: str | None,
        is_active: bool,
        is_superuser: bool,
    ) -> dict[str, Any]:
        """Create user from admin panel."""
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise ValueError("Email is required")
        existing = await self.db.scalar(select(User.id).where(User.email == normalized_email))
        if existing is not None:
            raise ValueError("Email already registered")
        validated_plan = self._validate_plan(plan)
        validated_language = self._validate_language(language)
        validated_timezone = self._normalize_timezone(timezone)
        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            name=self._normalize_optional_text(name),
            company_name=self._normalize_optional_text(company_name),
            plan=validated_plan,
            language=validated_language,
            timezone=validated_timezone,
            is_active=is_active,
            is_superuser=is_superuser,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return await self.get_user_detailed(user.id)

    async def get_user_detailed(self, user_id: UUID) -> dict[str, Any]:
        """Return single user in Users Management contract."""
        stmt = (
            select(
                User.id,
                User.email,
                User.name,
                User.company_name,
                User.plan,
                User.is_active,
                User.is_superuser,
                User.language,
                User.timezone,
                User.login_count,
                User.last_login_at,
                User.created_at,
                func.count(UserProduct.id).label("tracked_products"),
            )
            .outerjoin(UserProduct, UserProduct.user_id == User.id)
            .where(User.id == user_id)
            .group_by(User.id)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        row = result.mappings().first()
        if row is None:
            raise ValueError(f"User not found: {user_id}")
        return {
            "id": str(row["id"]),
            "email": row["email"],
            "name": row["name"],
            "company_name": row["company_name"],
            "plan": row["plan"],
            "is_active": bool(row["is_active"]),
            "is_superuser": bool(row["is_superuser"]),
            "language": row["language"],
            "timezone": row["timezone"],
            "login_count": int(row["login_count"] or 0),
            "tracked_products": int(row["tracked_products"] or 0),
            "last_login_at": self._to_iso(row["last_login_at"]),
            "created_at": self._to_iso(row["created_at"]),
        }

    async def update_user(
        self,
        user_id: UUID,
        *,
        email: str | None = None,
        name: str | None = None,
        company_name: str | None = None,
        plan: str | None = None,
        language: str | None = None,
        timezone: str | None = None,
        is_active: bool | None = None,
        is_superuser: bool | None = None,
    ) -> dict[str, Any]:
        """Update mutable user fields from admin panel."""
        user = await self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        if email is not None:
            normalized_email = email.strip().lower()
            if not normalized_email:
                raise ValueError("Email cannot be empty")
            existing = await self.db.scalar(
                select(User.id).where(User.email == normalized_email, User.id != user_id)
            )
            if existing is not None:
                raise ValueError("Email already registered")
            user.email = normalized_email
        if name is not None:
            user.name = self._normalize_optional_text(name)
        if company_name is not None:
            user.company_name = self._normalize_optional_text(company_name)
        if plan is not None:
            user.plan = self._validate_plan(plan)
        if language is not None:
            user.language = self._validate_language(language)
        if timezone is not None:
            user.timezone = self._normalize_timezone(timezone)
        if is_active is not None:
            user.is_active = bool(is_active)
        if is_superuser is not None:
            user.is_superuser = bool(is_superuser)
        await self.db.commit()
        return await self.get_user_detailed(user_id)

    async def set_user_active(
        self,
        user_id: UUID,
        *,
        is_active: bool,
        actor_user_id: UUID,
    ) -> dict[str, Any]:
        """Activate or deactivate user with safety checks."""
        if not is_active and user_id == actor_user_id:
            raise ValueError("You cannot deactivate your own account")
        user = await self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        if not is_active and user.is_superuser:
            superusers_count = await self.db.scalar(
                select(func.count(User.id)).where(User.is_superuser.is_(True), User.is_active.is_(True))
            )
            if int(superusers_count or 0) <= 1:
                raise ValueError("Cannot deactivate the last active superuser")
        user.is_active = is_active
        await self.db.commit()
        return await self.get_user_detailed(user_id)

    async def set_user_superuser(
        self,
        user_id: UUID,
        *,
        is_superuser: bool,
        actor_user_id: UUID,
    ) -> dict[str, Any]:
        """Grant or revoke superuser role with safety checks."""
        if not is_superuser and user_id == actor_user_id:
            raise ValueError("You cannot remove your own superuser role")
        user = await self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        if not is_superuser and user.is_superuser:
            superusers_count = await self.db.scalar(select(func.count(User.id)).where(User.is_superuser.is_(True)))
            if int(superusers_count or 0) <= 1:
                raise ValueError("Cannot remove role from the last superuser")
        user.is_superuser = is_superuser
        await self.db.commit()
        return await self.get_user_detailed(user_id)

    async def reset_user_password(
        self,
        user_id: UUID,
        *,
        new_password: str,
        force_password_change: bool,
    ) -> dict[str, Any]:
        """Admin password reset action."""
        user = await self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        user.password_hash = hash_password(new_password)
        user.force_password_change = force_password_change
        await self.db.commit()
        return await self.get_user_detailed(user_id)

    async def delete_user(self, user_id: UUID, *, actor_user_id: UUID) -> None:
        """Delete user with safety checks."""
        if user_id == actor_user_id:
            raise ValueError("You cannot delete your own account")
        user = await self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        if user.is_superuser:
            superusers_count = await self.db.scalar(select(func.count(User.id)).where(User.is_superuser.is_(True)))
            if int(superusers_count or 0) <= 1:
                raise ValueError("Cannot delete the last superuser")
        await self.db.delete(user)
        await self.db.commit()

    async def get_marketplaces_detailed(self, limit: int = 1000) -> list[dict[str, Any]]:
        """Detailed active marketplace list with scrape/discovery diagnostics."""
        safe_limit = max(1, min(limit, 5000))
        scrape_stats_sq = (
            select(
                ScrapeLog.marketplace_id.label("marketplace_id"),
                func.count(ScrapeLog.id).label("total_runs"),
                func.sum(case((ScrapeLog.status == "success", 1), else_=0)).label("success_runs"),
                func.max(ScrapeLog.created_at).label("last_log_at"),
            )
            .group_by(ScrapeLog.marketplace_id)
            .subquery()
        )
        active_listings_sq = (
            select(
                FactListing.marketplace_id.label("marketplace_id"),
                func.count(FactListing.id).label("active_listings"),
            )
            .where(FactListing.is_active.is_(True))
            .group_by(FactListing.marketplace_id)
            .subquery()
        )
        latest_error_sq = (
            select(
                ScrapeLog.marketplace_id.label("marketplace_id"),
                ScrapeLog.error_message.label("last_error_message"),
                func.row_number()
                .over(
                    partition_by=ScrapeLog.marketplace_id,
                    order_by=ScrapeLog.created_at.desc(),
                )
                .label("row_idx"),
            )
            .where(ScrapeLog.status != "success")
            .subquery()
        )

        stmt = (
            select(
                DimMarketplace.id,
                DimMarketplace.marketplace_code,
                DimMarketplace.name,
                DimMarketplace.domain,
                DimMarketplace.base_url,
                DimMarketplace.country_code,
                DimMarketplace.currency_code,
                DimMarketplace.scraper_type,
                DimMarketplace.requires_js,
                DimMarketplace.is_active,
                DimMarketplace.product_quota,
                DimMarketplace.products_in_pool,
                DimMarketplace.rate_limit_delay,
                DimMarketplace.last_discovery_at,
                DimMarketplace.last_discovery_status,
                DimMarketplace.last_discovery_products_found,
                DimMarketplace.last_scrape_at,
                DimMarketplace.last_scrape_status,
                scrape_stats_sq.c.total_runs,
                scrape_stats_sq.c.success_runs,
                scrape_stats_sq.c.last_log_at,
                active_listings_sq.c.active_listings,
                latest_error_sq.c.last_error_message,
            )
            .outerjoin(scrape_stats_sq, scrape_stats_sq.c.marketplace_id == DimMarketplace.id)
            .outerjoin(active_listings_sq, active_listings_sq.c.marketplace_id == DimMarketplace.id)
            .outerjoin(
                latest_error_sq,
                (latest_error_sq.c.marketplace_id == DimMarketplace.id)
                & (latest_error_sq.c.row_idx == 1),
            )
            .where(DimMarketplace.is_active.is_(True))
            .order_by(DimMarketplace.name.asc())
            .limit(safe_limit)
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
                    "id": str(row["id"]),
                    "marketplace_code": row["marketplace_code"],
                    "name": row["name"],
                    "domain": row["domain"],
                    "base_url": row["base_url"],
                    "country_code": row["country_code"],
                    "currency_code": row["currency_code"],
                    "scraper_type": row["scraper_type"],
                    "requires_js": bool(row["requires_js"]),
                    "is_active": bool(row["is_active"]),
                    "product_quota": int(row["product_quota"] or 0),
                    "products_in_pool": int(row["products_in_pool"] or 0),
                    "active_listings": int(row["active_listings"] or 0),
                    "rate_limit_delay": float(row["rate_limit_delay"] or 0.0),
                    "last_discovery_at": self._to_iso(row["last_discovery_at"]),
                    "last_discovery_status": row["last_discovery_status"],
                    "last_discovery_products_found": int(row["last_discovery_products_found"] or 0),
                    "last_scrape_at": self._to_iso(row["last_scrape_at"]),
                    "last_scrape_status": row["last_scrape_status"],
                    "last_log_at": self._to_iso(row["last_log_at"]),
                    "total_runs": total_runs,
                    "success_runs": success_runs,
                    "error_runs": max(0, total_runs - success_runs),
                    "success_rate": round(success_rate, 2),
                    "last_error_message": row["last_error_message"],
                }
            )
        return out

    async def get_job_live_feed(
        self,
        job_id: UUID,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Real-time feed for every persisted scrape step inside one pipeline job."""
        await self._fail_stale_running_pipeline_jobs()
        safe_limit = max(1, min(limit, 500))
        safe_offset = max(0, offset)

        job = await self.db.get(ScrapeJob, job_id)
        if job is None:
            raise ValueError(f"Scrape job not found: {job_id}")

        status_counts_result = await self.db.execute(
            select(ScrapeLog.status, func.count(ScrapeLog.id))
            .where(ScrapeLog.scrape_job_id == job.id)
            .group_by(ScrapeLog.status)
        )
        status_counts = {row[0]: int(row[1] or 0) for row in status_counts_result.all()}
        total_steps = int(sum(status_counts.values()))

        logs_total = await self.db.scalar(
            select(func.count(ScrapeLog.id)).where(ScrapeLog.scrape_job_id == job.id)
        )

        logs_result = await self.db.execute(
            select(
                ScrapeLog.id,
                ScrapeLog.created_at,
                ScrapeLog.status,
                ScrapeLog.listing_id,
                ScrapeLog.marketplace_id,
                ScrapeLog.url,
                ScrapeLog.price_found,
                ScrapeLog.in_stock_found,
                ScrapeLog.duration_ms,
                ScrapeLog.scraper_type,
                ScrapeLog.error_category,
                ScrapeLog.error_message,
                DimMarketplace.domain.label("marketplace_domain"),
            )
            .outerjoin(DimMarketplace, DimMarketplace.id == ScrapeLog.marketplace_id)
            .where(ScrapeLog.scrape_job_id == job.id)
            .order_by(ScrapeLog.created_at.desc(), ScrapeLog.id.desc())
            .offset(safe_offset)
            .limit(safe_limit)
        )
        rows = logs_result.mappings().all()

        steps = [
            {
                "event_id": int(row["id"]),
                "event_type": "listing_scrape",
                "created_at": self._to_iso(row["created_at"]),
                "status": row["status"],
                "listing_id": str(row["listing_id"]),
                "marketplace_id": str(row["marketplace_id"]),
                "marketplace_domain": row["marketplace_domain"],
                "url": row["url"],
                "price_found": float(row["price_found"]) if row["price_found"] is not None else None,
                "in_stock_found": row["in_stock_found"],
                "duration_ms": row["duration_ms"],
                "scraper_type": row["scraper_type"],
                "error_category": row["error_category"],
                "error_message": row["error_message"],
            }
            for row in rows
        ]

        metadata = self._extract_metadata(job.config)
        last_log_at = await self._job_last_log_at(job.id)
        metadata = self._merge_runtime_activity(
            job=job,
            metadata=metadata,
            last_log_at=last_log_at,
        )
        summary = metadata.get("summary", {}) if isinstance(metadata, dict) else {}
        timings = metadata.get("timings", {}) if isinstance(metadata, dict) else {}
        elapsed_seconds = self._duration_seconds(
            job.started_at,
            job.completed_at if job.completed_at is not None else datetime.now(UTC),
            None,
        )
        estimated_total_steps = int(job.total_listings or 0)
        estimated_remaining_seconds: float | None = None
        if (
            elapsed_seconds is not None
            and elapsed_seconds > 0
            and total_steps > 0
            and estimated_total_steps > total_steps
        ):
            speed = total_steps / elapsed_seconds
            if speed > 0:
                estimated_remaining_seconds = round((estimated_total_steps - total_steps) / speed, 3)

        warning_flags: list[str] = []
        missing_critical_count = int(status_counts.get("missing_critical_data", 0))
        technical_error_count = int(status_counts.get("technical_error", 0))
        error_ratio = (missing_critical_count + technical_error_count) / total_steps if total_steps > 0 else 0.0
        if missing_critical_count > 0:
            warning_flags.append("missing_currency_or_critical_fields")
        if technical_error_count > 0:
            warning_flags.append("technical_extraction_errors")
        if error_ratio >= 0.25 and total_steps >= 20:
            warning_flags.append("high_error_ratio")

        return {
            "job_id": str(job.id),
            "status": self._normalize_job_status(job.status),
            "current_stage": self._resolve_current_stage(
                metadata,
                self._normalize_job_status(job.status),
                last_log_at,
            ),
            "started_at": self._to_iso(job.started_at),
            "completed_at": self._to_iso(job.completed_at),
            "duration_seconds": self._duration_seconds(job.started_at, job.completed_at, job.duration_ms),
            "total_steps": total_steps,
            "status_counts": status_counts,
            "summary": {
                "listings_created": int(summary.get("listings_created", job.total_listings or 0)),
                "prices_saved": int(summary.get("prices_saved", job.successful or 0)),
                "errors_count": int(summary.get("errors_count", job.failed or 0)),
            },
            "timings": {
                "discovery_ms": int(timings.get("discovery_ms", 0)),
                "scrape_ms": int(timings.get("scrape_ms", 0)),
                "persist_ms": int(timings.get("persist_ms", 0)),
                "total_ms": int(timings.get("total_ms", job.duration_ms or 0)),
            },
            "estimated_total_steps": estimated_total_steps if estimated_total_steps > 0 else None,
            "estimated_remaining_seconds": estimated_remaining_seconds,
            "warning_flags": warning_flags,
            "last_activity_at": metadata.get("last_activity_at"),
            "steps": steps,
            "paging": {
                "limit": safe_limit,
                "offset": safe_offset,
                "total": int(logs_total or 0),
                "has_more": safe_offset + len(steps) < int(logs_total or 0),
            },
        }

    async def get_active_pipeline_job(self) -> dict[str, Any] | None:
        """Return currently running full pipeline job, if any."""
        await self._fail_stale_running_pipeline_jobs()
        result = await self.db.execute(
            select(ScrapeJob)
            .where(
                ScrapeJob.job_type == self.TEST_PIPELINE_JOB_TYPE,
                ScrapeJob.status == "running",
            )
            .order_by(ScrapeJob.started_at.desc().nullslast())
            .limit(1)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        metadata = self._extract_metadata(job.config)
        last_log_at = await self._job_last_log_at(job.id)
        metadata = self._merge_runtime_activity(
            job=job,
            metadata=metadata,
            last_log_at=last_log_at,
        )
        return {
            "job_id": str(job.id),
            "status": self._normalize_job_status(job.status),
            "current_stage": self._resolve_current_stage(
                metadata,
                self._normalize_job_status(job.status),
                last_log_at,
            ),
            "started_at": self._to_iso(job.started_at),
            "metadata": metadata,
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
            "last_activity_at": None,
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
    def _validate_plan(value: str) -> str:
        normalized = (value or "").strip().lower()
        try:
            return UserPlan(normalized).value
        except ValueError as exc:
            raise ValueError(
                "Invalid plan. Allowed: trial, starter, business, pro, enterprise"
            ) from exc

    @staticmethod
    def _validate_language(value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in ALLOWED_LANGUAGE_CODES:
            raise ValueError(
                f"Invalid language. Allowed: {', '.join(sorted(ALLOWED_LANGUAGE_CODES))}"
            )
        return normalized

    @staticmethod
    def _normalize_timezone(value: str | None) -> str:
        normalized = (value or "UTC").strip()
        if not normalized:
            return "UTC"
        if len(normalized) > 50:
            raise ValueError("Timezone exceeds maximum length (50)")
        return normalized

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

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

    def _resolve_current_stage(
        self,
        metadata: dict[str, Any],
        normalized_status: str,
        last_log_at: datetime | None,
    ) -> str | None:
        stage = self._current_stage(metadata)
        if normalized_status != "running":
            return stage
        if stage in {"queued", None} and last_log_at is not None:
            return "scrape"
        return stage

    async def _job_last_log_at(self, job_id: UUID) -> datetime | None:
        return await self.db.scalar(
            select(func.max(ScrapeLog.created_at)).where(ScrapeLog.scrape_job_id == job_id)
        )

    def _merge_runtime_activity(
        self,
        *,
        job: ScrapeJob,
        metadata: dict[str, Any],
        last_log_at: datetime | None,
    ) -> dict[str, Any]:
        out = dict(metadata)
        if out.get("last_activity_at"):
            return out
        fallback = last_log_at or job.started_at
        out["last_activity_at"] = self._to_iso(fallback)
        return out

    async def _fail_stale_running_pipeline_jobs(self) -> None:
        """Mark stale running jobs as failed when no activity is observed."""
        timeout_s = max(int(self.STALE_PIPELINE_TIMEOUT_MINUTES), 1) * 60
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(ScrapeJob)
            .where(
                ScrapeJob.job_type == self.TEST_PIPELINE_JOB_TYPE,
                ScrapeJob.status == "running",
            )
            .order_by(ScrapeJob.started_at.asc().nullslast())
        )
        running_jobs = list(result.scalars().all())
        changed = False
        for job in running_jobs:
            metadata = self._extract_metadata(job.config)
            last_log_at = await self._job_last_log_at(job.id)
            activity_iso = metadata.get("last_activity_at")
            activity_dt: datetime | None = None
            if isinstance(activity_iso, str) and activity_iso.strip():
                try:
                    activity_dt = datetime.fromisoformat(activity_iso)
                except ValueError:
                    activity_dt = None
            activity_dt = activity_dt or last_log_at or job.started_at
            if activity_dt is None:
                continue
            idle_s = (now - activity_dt).total_seconds()
            if idle_s < timeout_s:
                continue

            normalized = self._normalize_job_status(job.status)
            if normalized != "running":
                continue
            stale_metadata = dict(metadata)
            stale_metadata["current_stage"] = "failed"
            stale_metadata["last_activity_at"] = self._to_iso(activity_dt)
            stale_metadata["error"] = (
                f"stale_pipeline_timeout: idle_for_seconds={int(idle_s)} "
                f"threshold_seconds={timeout_s}"
            )
            job.status = "failed"
            job.completed_at = now
            job.duration_ms = (
                int((now - job.started_at).total_seconds() * 1000) if job.started_at is not None else None
            )
            job.config = {"metadata": stale_metadata}
            changed = True
        if changed:
            await self.db.commit()

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

