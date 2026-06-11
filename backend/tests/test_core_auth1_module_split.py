"""
CORE-AUTH1 invariants (framework-light: no DB / no HTTP).

Verifies the auth surface extraction:

1. The new ``app.modules.auth`` module imports cleanly with a clean public
   surface (api / service / schemas).
2. The four canonical /auth/* paths (register, login, change-initial-password,
   refresh) are still mounted under /api/auth/* exactly.
3. The remaining core routes (/me GET+PUT, /auth/telegram-link,
   /auth/telegram-disconnect) still mount from ``app.modules.core.api_auth``
   (they migrate in the users/telegram passes).
4. The old import path ``app.modules.core.auth.service`` is gone; every
   previous importer (common.deps, core.admin_service, admin.parsing_admin,
   core.api_auth-callers) points at ``app.modules.auth.service``.
5. The shared language / ai_tone validators live in ``app.common.validation``
   (Tier-0), and both UserRegister (auth) and UserUpdate (core) accept valid
   languages and reject invalid ones via the same validator.
6. The trimmed ``core.schemas`` no longer carries the auth-only schemas
   (UserRegister/UserLogin/TokenResponse/RefreshTokenRequest/
   ChangeInitialPasswordRequest); ``auth.schemas`` does.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from app.main import app

CORE_DIR = Path(__file__).resolve().parents[1] / "app" / "modules" / "core"


# 1. auth module surface ------------------------------------------------------

def test_auth_module_imports_cleanly() -> None:
    api = importlib.import_module("app.modules.auth.api")
    service = importlib.import_module("app.modules.auth.service")
    schemas = importlib.import_module("app.modules.auth.schemas")

    assert hasattr(api, "router")
    for fn in ("hash_password", "verify_password", "create_access_token", "create_refresh_token", "decode_token"):
        assert hasattr(service, fn), f"auth.service is missing {fn}"
    for name in ("UserRegister", "UserLogin", "TokenResponse", "RefreshTokenRequest", "ChangeInitialPasswordRequest"):
        assert hasattr(schemas, name), f"auth.schemas is missing {name}"


def test_auth_router_owns_only_the_four_extracted_routes() -> None:
    from app.modules.auth.api import router

    pairs = sorted(
        {
            (",".join(sorted(r.methods - {"HEAD"})), r.path)
            for r in router.routes
            if isinstance(r, APIRoute)
        }
    )
    assert pairs == [
        ("POST", "/auth/change-initial-password"),
        ("POST", "/auth/login"),
        ("POST", "/auth/refresh"),
        ("POST", "/auth/register"),
    ], f"auth.api router should own only the four extracted routes; got {pairs}"


# 2. /api/auth/* paths preserved ----------------------------------------------

def test_auth_paths_preserved_under_api() -> None:
    inventory = sorted(
        {
            (",".join(sorted(r.methods - {"HEAD"})), r.path)
            for r in app.routes
            if isinstance(r, APIRoute) and r.path.startswith("/api/auth/")
        }
    )
    assert inventory == [
        ("GET", "/api/auth/me"),
        ("POST", "/api/auth/change-initial-password"),
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/refresh"),
        ("POST", "/api/auth/register"),
        ("POST", "/api/auth/telegram-disconnect"),
        ("POST", "/api/auth/telegram-link"),
        ("PUT", "/api/auth/me"),
    ], f"/api/auth/* inventory drifted: {inventory}"


# 3. core/api_auth.py still serves the not-yet-migrated routes ---------------

def test_core_api_auth_still_owns_me_and_telegram_routes() -> None:
    from app.modules.core.api_auth import router as core_router

    pairs = sorted(
        {
            (",".join(sorted(r.methods - {"HEAD"})), r.path)
            for r in core_router.routes
            if isinstance(r, APIRoute)
        }
    )
    assert pairs == [
        ("GET", "/auth/me"),
        ("POST", "/auth/telegram-disconnect"),
        ("POST", "/auth/telegram-link"),
        ("PUT", "/auth/me"),
    ], f"core/api_auth.py drifted from the expected residual surface: {pairs}"


# 4. old import path gone + every prior importer repathed ---------------------

def test_old_core_auth_service_path_unimportable() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.modules.core.auth.service")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.modules.core.auth")


def test_old_core_auth_directory_gone() -> None:
    assert not (CORE_DIR / "auth").exists(), (
        "core/auth/ must be deleted after CORE-AUTH1 (service moved out)"
    )


@pytest.mark.parametrize(
    "module_name, attr",
    [
        ("app.common.deps", "decode_token"),
        ("app.modules.core.admin_service", "hash_password"),
        ("app.modules.admin.parsing_admin", "hash_password"),
    ],
)
def test_importers_repathed_to_auth_service(module_name: str, attr: str) -> None:
    """Each prior importer must now resolve ``attr`` to the new auth.service module."""
    module = importlib.import_module(module_name)
    target = importlib.import_module("app.modules.auth.service")
    assert getattr(module, attr) is getattr(target, attr), (
        f"{module_name}.{attr} is not the same object as app.modules.auth.service.{attr}"
    )


# 5. shared validators -------------------------------------------------------

def test_shared_validators_live_in_common_validation() -> None:
    validation = importlib.import_module("app.common.validation")
    assert hasattr(validation, "validate_language")
    assert hasattr(validation, "validate_ai_tone")
    assert "en" in validation.ALLOWED_LANGUAGE_CODES
    assert "concise" in validation.AI_TONE_VALUES


def test_user_register_uses_common_validator() -> None:
    from pydantic import ValidationError

    from app.modules.auth.schemas import UserRegister

    UserRegister(
        email="a@b.io",
        password="A_strong_one1",
        name=None,
        company_name=None,
        language="en",
    )
    with pytest.raises(ValidationError):
        UserRegister(
            email="a@b.io",
            password="A_strong_one1",
            name=None,
            company_name=None,
            language="xx",
        )


def test_user_update_uses_common_validator() -> None:
    from pydantic import ValidationError

    from app.modules.core.schemas import UserUpdate

    UserUpdate(language="ru")
    UserUpdate(ai_tone="balanced")
    with pytest.raises(ValidationError):
        UserUpdate(language="xx")
    with pytest.raises(ValidationError):
        UserUpdate(ai_tone="evangelical")


# 6. trimmed core/schemas no longer owns auth-only schemas --------------------

@pytest.mark.parametrize(
    "name",
    [
        "UserRegister",
        "UserLogin",
        "TokenResponse",
        "RefreshTokenRequest",
        "ChangeInitialPasswordRequest",
    ],
)
def test_auth_only_schemas_left_core(name: str) -> None:
    core_schemas = importlib.import_module("app.modules.core.schemas")
    assert not hasattr(core_schemas, name), (
        f"core.schemas.{name} should have moved to app.modules.auth.schemas"
    )
    auth_schemas = importlib.import_module("app.modules.auth.schemas")
    assert hasattr(auth_schemas, name)


def test_core_schemas_keeps_user_response_and_update() -> None:
    core_schemas = importlib.import_module("app.modules.core.schemas")
    assert hasattr(core_schemas, "UserResponse")
    assert hasattr(core_schemas, "UserUpdate")
    assert hasattr(core_schemas, "TelegramLinkResponse")
