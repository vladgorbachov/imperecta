"""Admin API for parsing administration workflows."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.modules.admin.parsing_admin import ParsingAdminService
from app.modules.scraper.tasks import orchestrator_tick

router = APIRouter(
    prefix="/admin/parsing",
    tags=["admin-parsing"],
    dependencies=[Depends(get_current_superuser)],
)


class RunPipelineRequest(BaseModel):
    """Optional subset of dim_marketplace.marketplace_code values for this run."""

    marketplace_codes: list[str] | None = Field(
        default=None,
        max_length=50,
        description="If set, discovery/scrape only these marketplace_code values.",
    )


class SitemapEnumerateRequest(BaseModel):
    """Sitemap-full onboarding trigger (SITEMAP_FIRST slice 1)."""

    marketplace_codes: list[str] = Field(min_length=1, max_length=20)
    max_urls: int = Field(default=500_000, ge=1_000, le=2_000_000)


@router.get("/test-marketplaces")
async def get_test_marketplaces(
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> list[dict]:
    """Frontend table source for parsing admin marketplace cards."""
    service = ParsingAdminService(db)
    return await service.get_test_marketplaces()


async def _enqueue_pipeline_run(
    db: DbSession,
    body: RunPipelineRequest | None,
) -> dict:
    service = ParsingAdminService(db)
    codes = body.marketplace_codes if body is not None else None
    try:
        created = await service.trigger_full_pipeline_test(marketplace_codes=codes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Pipeline dispatch: the distributed tick orchestrator is the only path.
    orchestrator_tick.apply_async([created["job_id"]])
    return created


@router.post("/run-pipeline")
async def run_pipeline(
    _current_user: CurrentSuperuser,
    db: DbSession,
    body: RunPipelineRequest | None = None,
) -> dict:
    """Create parent job and enqueue full admin pipeline (manual data collection)."""
    return await _enqueue_pipeline_run(db, body)


@router.post("/sitemap-enumerate")
async def trigger_sitemap_enumerate(
    body: SitemapEnumerateRequest,
    _current_user: CurrentSuperuser,
) -> dict:
    """Dispatch sitemap-full catalog enumeration for the given shops.

    One Celery task per marketplace (independent, idempotent — dedupe by
    url_hash makes reruns pick up only what previous runs missed). Progress
    is visible via pool counts (/pool/marketplace-stats) and worker logs.
    """
    from app.workers.onboarding_tasks import sitemap_enumerate_marketplace

    dispatched = []
    for code in body.marketplace_codes:
        async_result = sitemap_enumerate_marketplace.apply_async(
            [code.strip()],
            kwargs={"max_urls": body.max_urls},
        )
        dispatched.append({"marketplace_code": code.strip(), "task_id": async_result.id})
    return {"dispatched": dispatched, "max_urls": body.max_urls}


class HarvestListsRequest(BaseModel):
    """List-page price harvest trigger (SITEMAP_FIRST slice 2)."""

    marketplace_codes: list[str] = Field(min_length=1, max_length=20)
    pages_per_shop: int = Field(default=20, ge=1, le=500)


@router.post("/harvest-lists")
async def trigger_harvest_lists(
    body: HarvestListsRequest,
    _current_user: CurrentSuperuser,
) -> dict:
    """Dispatch list-page price harvesting for the given shops."""
    from app.workers.harvest_tasks import harvest_list_pages

    dispatched = []
    for code in body.marketplace_codes:
        async_result = harvest_list_pages.apply_async(
            [code.strip()],
            kwargs={"limit": body.pages_per_shop},
        )
        dispatched.append({"marketplace_code": code.strip(), "task_id": async_result.id})
    return {"dispatched": dispatched, "pages_per_shop": body.pages_per_shop}


@router.get("/pipeline-runs")
async def get_pipeline_runs(
    _current_user: CurrentSuperuser,
    db: DbSession,
    limit: int = Query(10, ge=1, le=200),
) -> list[dict]:
    """Pipeline run history for admin Data Collection tab (latest runs)."""
    service = ParsingAdminService(db)
    return await service.get_test_runs(limit=limit)


@router.post("/cancel-active-job")
async def cancel_active_job(
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Cancel the currently running admin pipeline job."""
    service = ParsingAdminService(db)
    try:
        return await service.cancel_active_pipeline_job()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/job-status/{job_id}")
async def get_job_status(
    job_id: UUID,
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Frontend polling endpoint (4-5s interval) for in-flight run state."""
    service = ParsingAdminService(db)
    try:
        return await service.get_job_status(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/worker-log-relay")
async def get_worker_log_relay(
    _current_user: CurrentSuperuser,
    after: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    job_id: UUID | None = Query(default=None),
) -> dict:
    """Pollable relay of celery worker deploy log lines (Redis buffer)."""
    payload = ParsingAdminService.get_worker_log_relay(after=after, limit=limit)
    if job_id is not None:
        job_key = str(job_id)
        payload["lines"] = [
            line for line in payload.get("lines", []) if line.get("job_id") in {job_key, None}
        ]
        if payload["lines"]:
            payload["next_cursor"] = int(payload["lines"][-1]["seq"])
    payload["visible_lines"] = 3
    return payload


@router.get("/marketplaces-detailed")
async def get_marketplaces_detailed(
    _current_user: CurrentSuperuser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """Paginated marketplace list for admin Market Overview."""
    service = ParsingAdminService(db)
    return await service.get_marketplaces_detailed(page=page, page_size=page_size)


@router.get("/job-live-feed/{job_id}")
async def get_job_live_feed(
    job_id: UUID,
    _current_user: CurrentSuperuser,
    db: DbSession,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """Real-time per-step job feed from scrape_logs."""
    service = ParsingAdminService(db)
    try:
        return await service.get_job_live_feed(job_id, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/active-job")
async def get_active_job(
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Current running full pipeline job for page restore after reload."""
    service = ParsingAdminService(db)
    active = await service.get_active_pipeline_job()
    return {"active_job": active}

