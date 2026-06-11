"""Users API: self profile (/users/me) and admin user CRUD (/admin/users/*).

CORE-USERS1 extracted these from core/api_auth.py and admin/api_parsing.py;
paths changed (/auth/me -> /users/me, /admin/parsing/users* -> /admin/users/*)
but request/response shapes are preserved (the frontend repoints to the new
URLs in the same pass).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.common.deps import CurrentSuperuser, CurrentUser, DbSession, get_current_superuser
from app.modules.users.schemas import (
    AdminUserCreateRequest,
    AdminUserPasswordResetRequest,
    AdminUserRoleRequest,
    AdminUserStatusRequest,
    AdminUserUpdateRequest,
    UserResponse,
    UserUpdate,
)
from app.modules.users.service import UsersAdminService, UsersService

self_router = APIRouter(prefix="/users", tags=["users"])
admin_router = APIRouter(
    prefix="/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(get_current_superuser)],
)


def _raise_user_crud_error(exc: ValueError) -> None:
    """Map admin-user-CRUD ValueErrors to HTTP status codes:
    'User not found:' -> 404, everything else (validation, security) -> 400.
    """
    message = str(exc)
    if message.startswith("User not found:"):
        raise HTTPException(status_code=404, detail=message) from exc
    raise HTTPException(status_code=400, detail=message) from exc


# ---- /users/me (self profile) ------------------------------------------------

@self_router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return UsersService.build_user_response(current_user)


@self_router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    service = UsersService(db)
    return await service.update_me(current_user, data.model_dump(exclude_unset=True))


# ---- /admin/users/* (admin user CRUD) ---------------------------------------

@admin_router.get("")
async def get_users_detailed(
    _current_user: CurrentSuperuser,
    db: DbSession,
    limit: int = Query(500, ge=1, le=2000),
) -> list[dict]:
    """Detailed users list for admin diagnostics UI."""
    service = UsersAdminService(db)
    return await service.get_users_detailed(limit=limit)


@admin_router.post("")
async def create_user(
    payload: AdminUserCreateRequest,
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Create user from Users Management tab."""
    service = UsersAdminService(db)
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


@admin_router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    payload: AdminUserUpdateRequest,
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Update user profile, plan and flags from Users Management tab."""
    service = UsersAdminService(db)
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


@admin_router.patch("/{user_id}/status")
async def set_user_status(
    user_id: UUID,
    payload: AdminUserStatusRequest,
    current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Activate/deactivate user with safety checks."""
    service = UsersAdminService(db)
    try:
        return await service.set_user_active(
            user_id,
            is_active=payload.is_active,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        _raise_user_crud_error(exc)
        raise


@admin_router.patch("/{user_id}/role")
async def set_user_role(
    user_id: UUID,
    payload: AdminUserRoleRequest,
    current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Grant or revoke superuser role."""
    service = UsersAdminService(db)
    try:
        return await service.set_user_superuser(
            user_id,
            is_superuser=payload.is_superuser,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        _raise_user_crud_error(exc)
        raise


@admin_router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: UUID,
    payload: AdminUserPasswordResetRequest,
    _current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Reset user password from Users Management."""
    service = UsersAdminService(db)
    try:
        return await service.reset_user_password(
            user_id,
            new_password=payload.new_password,
            force_password_change=payload.force_password_change,
        )
    except ValueError as exc:
        _raise_user_crud_error(exc)
        raise


@admin_router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: CurrentSuperuser,
    db: DbSession,
) -> dict:
    """Delete user from Users Management."""
    service = UsersAdminService(db)
    try:
        await service.delete_user(user_id, actor_user_id=current_user.id)
    except ValueError as exc:
        _raise_user_crud_error(exc)
        raise
    return {"deleted": True}
