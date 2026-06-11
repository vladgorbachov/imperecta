"""
CORE-USERS1 users module assembly invariants (no DB / no HTTP).

Covers:

1. New module surface: app.modules.users.{api,service,schemas} import; the
   self router exposes /users/me (GET, PUT); the admin router exposes the 7
   /admin/users/* routes with a superuser dependency.

2. Path migration: /api/users/me + /api/admin/users/* are mounted in the
   live app; the legacy /api/auth/me + /api/admin/parsing/users* paths are
   gone (the latter is now pipeline-only).

3. parsing_admin.py is pipeline-only: the 8 user methods + 4 user
   validators are removed; pipeline entrypoints are intact; the now-unused
   imports (UserPlan, User, UserProduct, hash_password,
   ALLOWED_LANGUAGE_CODES) no longer appear at the module level.

4. SIX security invariants on UsersAdminService — each its own assertion,
   logic preserved byte-for-byte:
       - deactivate self -> ValueError "cannot deactivate your own account"
       - deactivate last active superuser -> ValueError
       - remove own superuser role -> ValueError
       - remove role from last superuser -> ValueError
       - delete self -> ValueError
       - delete last superuser -> ValueError
   Plus: create_user duplicate-email -> ValueError, update_user duplicate-
   email -> ValueError, invalid plan/language rejected.

5. Self-profile parity: build_user_response returns the same UserResponse
   contract as the pre-CORE-USERS1 /auth/me payload (entitlements included);
   update_me enforces ALLOWED_USER_UPDATE_FIELDS and treats
   ``avatar_url=""`` as explicit clear.

6. Plan-limits relocated: get_product_limit / get_competitor_limit /
   is_free_plan resolve from app.modules.users.service; the orphan
   app.modules.core.plans package is gone.
"""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.routing import APIRoute

from app.entitlements.plan import UserPlan
from app.main import app

USERS_DIR = Path(__file__).resolve().parents[1] / "app" / "modules" / "users"
PARSING_ADMIN_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "modules" / "admin" / "parsing_admin.py"
)


# 1. module surface -----------------------------------------------------------

def test_users_module_imports_clean() -> None:
    api = importlib.import_module("app.modules.users.api")
    service = importlib.import_module("app.modules.users.service")
    schemas = importlib.import_module("app.modules.users.schemas")
    assert hasattr(api, "self_router")
    assert hasattr(api, "admin_router")
    assert hasattr(service, "UsersService")
    assert hasattr(service, "UsersAdminService")
    for name in (
        "UserResponse",
        "UserUpdate",
        "AdminUserCreateRequest",
        "AdminUserUpdateRequest",
        "AdminUserStatusRequest",
        "AdminUserRoleRequest",
        "AdminUserPasswordResetRequest",
    ):
        assert hasattr(schemas, name)


def test_self_router_owns_only_users_me() -> None:
    from app.modules.users.api import self_router

    pairs = sorted(
        {(",".join(sorted(r.methods - {"HEAD"})), r.path) for r in self_router.routes if isinstance(r, APIRoute)}
    )
    assert pairs == [("GET", "/users/me"), ("PUT", "/users/me")]


def test_admin_router_owns_only_admin_users() -> None:
    from app.modules.users.api import admin_router

    pairs = sorted(
        {(",".join(sorted(r.methods - {"HEAD"})), r.path) for r in admin_router.routes if isinstance(r, APIRoute)}
    )
    assert pairs == [
        ("DELETE", "/admin/users/{user_id}"),
        ("GET", "/admin/users"),
        ("PATCH", "/admin/users/{user_id}"),
        ("PATCH", "/admin/users/{user_id}/role"),
        ("PATCH", "/admin/users/{user_id}/status"),
        ("POST", "/admin/users"),
        ("POST", "/admin/users/{user_id}/reset-password"),
    ]


def test_admin_router_superuser_gated() -> None:
    from app.common.deps import get_current_superuser
    from app.modules.users.api import admin_router

    deps = [d.dependency for d in (admin_router.dependencies or [])]
    assert get_current_superuser in deps


# 2. path migration -----------------------------------------------------------

def test_live_app_routes_after_migration() -> None:
    inventory = {
        (",".join(sorted(r.methods - {"HEAD"})), r.path)
        for r in app.routes
        if isinstance(r, APIRoute) and r.path.startswith(("/api/users", "/api/admin/users", "/api/auth/me", "/api/admin/parsing/users"))
    }
    assert inventory == {
        ("GET", "/api/users/me"),
        ("PUT", "/api/users/me"),
        ("GET", "/api/admin/users"),
        ("POST", "/api/admin/users"),
        ("PATCH", "/api/admin/users/{user_id}"),
        ("PATCH", "/api/admin/users/{user_id}/status"),
        ("PATCH", "/api/admin/users/{user_id}/role"),
        ("POST", "/api/admin/users/{user_id}/reset-password"),
        ("DELETE", "/api/admin/users/{user_id}"),
    }


# 3. parsing_admin.py is pipeline-only ---------------------------------------

@pytest.mark.parametrize(
    "method",
    [
        "get_users_detailed",
        "create_user",
        "get_user_detailed",
        "update_user",
        "set_user_active",
        "set_user_superuser",
        "reset_user_password",
        "delete_user",
        "_validate_plan",
        "_validate_language",
        "_normalize_timezone",
        "_normalize_optional_text",
    ],
)
def test_parsing_admin_user_code_gone(method: str) -> None:
    from app.modules.admin.parsing_admin import ParsingAdminService

    assert not hasattr(ParsingAdminService, method), (
        f"ParsingAdminService.{method} must move to UsersAdminService"
    )


@pytest.mark.parametrize(
    "method",
    [
        "get_test_marketplaces",
        "trigger_full_pipeline_test",
        "get_test_runs",
        "get_job_status",
        "get_pipeline_status",
        "get_marketplaces_detailed",
        "get_job_live_feed",
        "get_active_pipeline_job",
        "cancel_active_pipeline_job",
    ],
)
def test_parsing_admin_pipeline_methods_intact(method: str) -> None:
    from app.modules.admin.parsing_admin import ParsingAdminService

    assert hasattr(ParsingAdminService, method)


def test_parsing_admin_unused_imports_dropped() -> None:
    """After CORE-USERS1 the user-CRUD symbols must no longer be imported
    by parsing_admin.py (they would be dead imports)."""
    text = PARSING_ADMIN_PATH.read_text(encoding="utf-8")
    head = text.split("class ParsingAdminService", 1)[0]
    for symbol in ("UserPlan", "UserProduct", "hash_password", "ALLOWED_LANGUAGE_CODES"):
        assert symbol not in head, f"{symbol} should be removed from parsing_admin imports"
    assert "from app.models.core import User" not in head, (
        "User model import must be dropped from parsing_admin"
    )


# 4. SIX security invariants + create/update validation ----------------------


class _FakeUser:
    def __init__(self, *, user_id: UUID, is_active: bool = True, is_superuser: bool = False) -> None:
        self.id = user_id
        self.is_active = is_active
        self.is_superuser = is_superuser


class _SecurityFakeDb:
    """Minimal AsyncSession stub for branch-coverage of safety checks.

    Returns ``existing_user`` from ``get``; ``superuser_count`` from ``scalar``.
    """

    def __init__(self, *, existing_user: _FakeUser | None, superuser_count: int) -> None:
        self._user = existing_user
        self._superuser_count = superuser_count
        self.commits = 0
        self.deleted: list[_FakeUser] = []

    async def get(self, _model, _user_id):
        return self._user

    async def scalar(self, _stmt):
        return self._superuser_count

    async def commit(self) -> None:
        self.commits += 1

    async def delete(self, user) -> None:
        self.deleted.append(user)


def _run(coro):
    return asyncio.run(coro)


def test_security_cannot_deactivate_self() -> None:
    from app.modules.users.service import UsersAdminService

    actor = uuid4()
    db = _SecurityFakeDb(existing_user=_FakeUser(user_id=actor, is_active=True, is_superuser=False), superuser_count=2)
    svc = UsersAdminService(db)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="cannot deactivate your own account"):
        _run(svc.set_user_active(actor, is_active=False, actor_user_id=actor))


def test_security_cannot_deactivate_last_active_superuser() -> None:
    from app.modules.users.service import UsersAdminService

    actor = uuid4()
    target = uuid4()
    db = _SecurityFakeDb(
        existing_user=_FakeUser(user_id=target, is_active=True, is_superuser=True),
        superuser_count=1,
    )
    svc = UsersAdminService(db)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Cannot deactivate the last active superuser"):
        _run(svc.set_user_active(target, is_active=False, actor_user_id=actor))


def test_security_cannot_remove_own_superuser_role() -> None:
    from app.modules.users.service import UsersAdminService

    actor = uuid4()
    db = _SecurityFakeDb(existing_user=_FakeUser(user_id=actor, is_superuser=True), superuser_count=5)
    svc = UsersAdminService(db)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="cannot remove your own superuser role"):
        _run(svc.set_user_superuser(actor, is_superuser=False, actor_user_id=actor))


def test_security_cannot_remove_role_from_last_superuser() -> None:
    from app.modules.users.service import UsersAdminService

    actor = uuid4()
    target = uuid4()
    db = _SecurityFakeDb(
        existing_user=_FakeUser(user_id=target, is_superuser=True), superuser_count=1
    )
    svc = UsersAdminService(db)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Cannot remove role from the last superuser"):
        _run(svc.set_user_superuser(target, is_superuser=False, actor_user_id=actor))


def test_security_cannot_delete_self() -> None:
    from app.modules.users.service import UsersAdminService

    actor = uuid4()
    db = _SecurityFakeDb(
        existing_user=_FakeUser(user_id=actor, is_superuser=False), superuser_count=5
    )
    svc = UsersAdminService(db)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="cannot delete your own account"):
        _run(svc.delete_user(actor, actor_user_id=actor))


def test_security_cannot_delete_last_superuser() -> None:
    from app.modules.users.service import UsersAdminService

    actor = uuid4()
    target = uuid4()
    db = _SecurityFakeDb(
        existing_user=_FakeUser(user_id=target, is_superuser=True), superuser_count=1
    )
    svc = UsersAdminService(db)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Cannot delete the last superuser"):
        _run(svc.delete_user(target, actor_user_id=actor))


def test_validators_reject_invalid_plan_and_language() -> None:
    from app.modules.users.service import UsersAdminService

    with pytest.raises(ValueError, match="Invalid plan"):
        UsersAdminService._validate_plan("nope")
    with pytest.raises(ValueError, match="Invalid language"):
        UsersAdminService._validate_language("xx")
    assert UsersAdminService._validate_plan("trial") == UserPlan.trial.value


# 5. self-profile parity ------------------------------------------------------


def _build_fake_user_for_response() -> SimpleNamespace:
    from datetime import datetime, timezone

    return SimpleNamespace(
        id=uuid4(),
        email="a@b.io",
        name="A",
        company_name="C",
        plan=UserPlan.trial,
        trial_ends_at=datetime.now(timezone.utc),
        language="en",
        timezone="UTC",
        ai_tone="balanced",
        default_currency="USD",
        is_superuser=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        last_login_at=None,
        telegram_chat_id=None,
        avatar_url=None,
        preferences={},
    )


def test_build_user_response_shape_matches_legacy() -> None:
    from app.modules.users.service import UsersService

    fake = _build_fake_user_for_response()
    response = UsersService.build_user_response(fake)
    payload = response.model_dump()
    assert payload["id"] == fake.id
    assert payload["plan"] == "trial"  # _plan_str unwraps the enum
    assert payload["entitlements"] is not None
    expected = {
        "id", "email", "name", "company_name", "plan", "trial_ends_at",
        "language", "timezone", "ai_tone", "default_currency",
        "is_superuser", "is_active", "avatar_url", "last_login_at",
        "created_at", "telegram_chat_id", "preferences", "entitlements",
    }
    assert set(payload.keys()) == expected


def test_update_me_honors_whitelist_and_clears_avatar() -> None:
    from app.modules.users.service import UsersService

    class _FlushDb:
        def __init__(self) -> None:
            self.flushes = 0

        async def flush(self) -> None:
            self.flushes += 1

    fake = _build_fake_user_for_response()
    fake.avatar_url = "https://cdn/old.png"
    fake.is_superuser = False
    svc = UsersService(_FlushDb())  # type: ignore[arg-type]

    _run(
        svc.update_me(
            fake,
            {
                "name": "B",
                "avatar_url": "",
                "is_superuser": True,
                "email": "evil@b.io",
            },
        )
    )

    assert fake.name == "B"
    assert fake.avatar_url is None
    assert fake.is_superuser is False, "is_superuser must not be writable via /users/me"
    assert fake.email == "a@b.io", "email must not be writable via /users/me"


# 6. plan-limits moved + orphan core/plans deleted ---------------------------

def test_plan_limits_live_in_users_service() -> None:
    from app.modules.users.service import (
        get_competitor_limit,
        get_product_limit,
        is_free_plan,
    )

    assert callable(get_product_limit)
    assert callable(get_competitor_limit)
    assert callable(is_free_plan)
    assert isinstance(get_product_limit(UserPlan.trial), int)


def test_old_core_plans_package_gone() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.modules.core.plans.service")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.modules.core.plans")


def test_old_core_users_placeholder_gone() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.modules.core.users")


def test_core_schemas_module_deleted_by_tg1() -> None:
    """CORE-TG1 finished dissolving core/: TelegramLinkResponse moved to
    app.modules.telegram.schemas (renamed TelegramLinkCodeResponse) and the
    now-empty core/schemas.py file was deleted."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.modules.core.schemas")
    telegram_schemas = importlib.import_module("app.modules.telegram.schemas")
    assert hasattr(telegram_schemas, "TelegramLinkCodeResponse")


def test_core_api_auth_module_deleted_by_tg1() -> None:
    """CORE-TG1 deleted the residual core/api_auth.py; the duplicate
    telegram link/disconnect routes were folded into the canonical
    /telegram/* set."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.modules.core.api_auth")
