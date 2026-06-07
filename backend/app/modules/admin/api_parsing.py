"""Admin API for parsing administration workflows."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from app.common.deps import CurrentSuperuser, DbSession, get_current_superuser
from app.config import Settings
from app.modules.admin.parsing_admin import ParsingAdminService
from app.modules.scraper.tasks import orchestrator_tick, run_full_pipeline_test

router = APIRouter(
    prefix="/admin/parsing",
    tags=["admin-parsing"],
    dependencies=[Depends(get_current_superuser)],
)


class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=100)
    company_name: str | None = Field(default=None, max_length=200)
    plan: str
    language: str
    timezone: str | None = Field(default="UTC", max_length=50)
    is_active: bool = True
    is_superuser: bool = False


class AdminUserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    name: str | None = Field(default=None, max_length=100)
    company_name: str | None = Field(default=None, max_length=200)
    plan: str | None = None
    language: str | None = None
    timezone: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None
    is_superuser: bool | None = None


class AdminUserStatusRequest(BaseModel):
    is_active: bool


class AdminUserRoleRequest(BaseModel):
    is_superuser: bool


class AdminUserPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
    force_password_change: bool = True


class RunPipelineRequest(BaseModel):
    """Optional subset of dim_marketplace.marketplace_code values for this run."""

    marketplace_codes: list[str] | None = Field(
        default=None,
        max_length=50,
        description="If set, discovery/scrape only these marketplace_code values.",
    )


RunFullPipelineTestRequest = RunPipelineRequest


def _raise_user_crud_error(exc: ValueError) -> None:
    message = str(exc)
    if message.startswith("User not found:"):
        raise HTTPException(status_code=404, detail=message) from exc
    raise HTTPException(status_code=400, detail=message) from exc


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

    # O3 feature flag: "tick" routes to the distributed orchestrator;
    # anything else (including missing/unset) falls back to the proven
    # monolithic full-pipeline task. Instant rollback by unsetting the env var.
    mode = (Settings().orchestrator_mode or "monolith").strip().lower()
    if mode == "tick":
        orchestrator_tick.apply_async([created["job_id"]])
    else:
        run_full_pipeline_test.delay(created["job_id"])
    return created


@router.post("/run-pipeline")
async def run_pipeline(
    _current_user: CurrentSuperuser,
    db: DbSession,
    body: RunPipelineRequest | None = None,
) -> dict:
    """Create parent job and enqueue full admin pipeline (manual data collection)."""
    return await _enqueue_pipeline_run(db, body)


@router.post("/run-full-test")
async def run_full_test(
    _current_user: CurrentSuperuser,
    db: DbSession,
    body: RunFullPipelineTestRequest | None = None,
) -> dict:
    """Deprecated alias for POST /run-pipeline."""
    return await _enqueue_pipeline_run(db, body)


@router.get("/pipeline-runs")
async def get_pipeline_runs(
    _current_user: CurrentSuperuser,
    db: DbSession,
    limit: int = Query(10, ge=1, le=200),
) -> list[dict]:
    """Pipeline run history for admin Data Collection tab (latest runs)."""
    service = ParsingAdminService(db)
    return await service.get_test_runs(limit=limit)


@router.get("/test-runs")
async def get_test_runs(
    _current_user: CurrentSuperuser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Deprecated alias for GET /pipeline-runs."""
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


@router.get("/users-detailed")
async def get_users_detailed(
    _current_user: CurrentSuperuser,
    db: DbSession,
    limit: int = Query(500, ge=1, le=2000),
) -> list[dict]:
    """Detailed users list for admin diagnostics UI."""
    service = ParsingAdminService(db)
    return await service.get_users_detailed(limit=limit)


@router.post("/users")
async def create_user(
    payload: AdminUserCreateRequest,
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Create user from Users Management tab."""
    service = ParsingAdminService(db)
    try:
        return await service.create_user(
            email=payload.email,
            password=payload.password,
            name=payload.name,
            company_name=payload.company_name,
            plan=payload.plan,
            language=payload.language,
            timezone=payload.timezone,
            is_active=payload.is_active,
            is_superuser=payload.is_superuser,
        )
    except ValueError as exc:
        _raise_user_crud_error(exc)
        raise


@router.patch("/users/{user_id}")
async def update_user(
    user_id: UUID,
    payload: AdminUserUpdateRequest,
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Update user profile, plan and flags from Users Management tab."""
    service = ParsingAdminService(db)
    try:
        return await service.update_user(
            user_id,
            email=str(payload.email) if payload.email is not None else None,
            name=payload.name,
            company_name=payload.company_name,
            plan=payload.plan,
            language=payload.language,
            timezone=payload.timezone,
            is_active=payload.is_active,
            is_superuser=payload.is_superuser,
        )
    except ValueError as exc:
        _raise_user_crud_error(exc)
        raise


@router.patch("/users/{user_id}/status")
async def set_user_status(
    user_id: UUID,
    payload: AdminUserStatusRequest,
    current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Activate/deactivate user with safety checks."""
    service = ParsingAdminService(db)
    try:
        return await service.set_user_active(
            user_id,
            is_active=payload.is_active,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        _raise_user_crud_error(exc)
        raise


@router.patch("/users/{user_id}/role")
async def set_user_role(
    user_id: UUID,
    payload: AdminUserRoleRequest,
    current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Grant or revoke superuser role."""
    service = ParsingAdminService(db)
    try:
        return await service.set_user_superuser(
            user_id,
            is_superuser=payload.is_superuser,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        _raise_user_crud_error(exc)
        raise


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: UUID,
    payload: AdminUserPasswordResetRequest,
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Reset user password from Users Management."""
    service = ParsingAdminService(db)
    try:
        return await service.reset_user_password(
            user_id,
            new_password=payload.new_password,
            force_password_change=payload.force_password_change,
        )
    except ValueError as exc:
        _raise_user_crud_error(exc)
        raise


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Delete user from Users Management."""
    service = ParsingAdminService(db)
    try:
        await service.delete_user(user_id, actor_user_id=current_user.id)
    except ValueError as exc:
        _raise_user_crud_error(exc)
        raise
    return {"deleted": True}


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


@router.get("/pipeline-status")
async def get_pipeline_status(
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """No-id status of the current pipeline (running → latest → idle) for the
    PipelineStatusPanel polling hook."""
    service = ParsingAdminService(db)
    return await service.get_pipeline_status()
