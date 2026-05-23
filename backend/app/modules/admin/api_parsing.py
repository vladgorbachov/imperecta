"""Admin API for parsing administration workflows."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.modules.admin.parsing_admin import ParsingAdminService
from app.modules.scraper.tasks import run_full_pipeline_test

router = APIRouter(
    prefix="/admin/parsing",
    tags=["admin-parsing"],
    dependencies=[Depends(get_current_superuser)],
)


@router.get("/test-marketplaces")
async def get_test_marketplaces(
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> list[dict]:
    """Frontend table source for parsing admin marketplace cards."""
    service = ParsingAdminService(db)
    return await service.get_test_marketplaces()


@router.post("/run-full-test")
async def run_full_test(
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Frontend action: create parent job and enqueue full pipeline task."""
    service = ParsingAdminService(db)
    try:
        created = await service.trigger_full_pipeline_test()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    run_full_pipeline_test.delay(created["job_id"])
    return created


@router.get("/test-runs")
async def get_test_runs(
    _current_user: CurrentSuperuser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Frontend run history list used below run button."""
    service = ParsingAdminService(db)
    return await service.get_test_runs(limit=limit)


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


@router.get("/users-detailed")
async def get_users_detailed(
    _current_user: CurrentSuperuser,
    db: DbSession,
    limit: int = Query(500, ge=1, le=2000),
) -> list[dict]:
    """Detailed users list for admin diagnostics UI."""
    service = ParsingAdminService(db)
    return await service.get_users_detailed(limit=limit)


@router.get("/marketplaces-detailed")
async def get_marketplaces_detailed(
    _current_user: CurrentSuperuser,
    db: DbSession,
    limit: int = Query(1000, ge=1, le=5000),
) -> list[dict]:
    """Detailed active marketplaces list for admin diagnostics UI."""
    service = ParsingAdminService(db)
    return await service.get_marketplaces_detailed(limit=limit)


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
