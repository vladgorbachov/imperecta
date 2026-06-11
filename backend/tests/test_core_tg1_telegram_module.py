"""CORE-TG1 invariants: telegram extracted as a Tier-1 module; the duplicate
linking surface is gone; core/ is fully dissolved (only the admin cluster
remains, parked for Phase 5).

Mirrors the structure of the M1/MP1/AI1/CORE-AUTH1/CORE-USERS1 invariant
suites: surface contracts + dead-path guards + a hardcoded-Russian guard
specific to this pass.
"""

from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.routing import APIRoute

from app.main import app


# ---------------------------------------------------------------------------
# 1. telegram/ surface
# ---------------------------------------------------------------------------


def test_telegram_module_imports_clean() -> None:
    """``app.modules.telegram.{api,schemas}`` import without side effects."""
    api = importlib.import_module("app.modules.telegram.api")
    schemas = importlib.import_module("app.modules.telegram.schemas")
    assert hasattr(api, "router")
    for symbol in (
        "TelegramLinkCodeResponse",
        "TelegramUnlinkResponse",
        "TelegramStatusResponse",
    ):
        assert hasattr(schemas, symbol), f"telegram.schemas.{symbol} missing"


def test_telegram_router_mounts_canonical_four_routes() -> None:
    """All four canonical routes are mounted exactly once under /api/telegram/*."""
    inventory = sorted(
        {
            (",".join(sorted(r.methods - {"HEAD"})), r.path)
            for r in app.routes
            if isinstance(r, APIRoute) and r.path.startswith("/api/telegram/")
        }
    )
    assert inventory == [
        ("GET", "/api/telegram/status"),
        ("POST", "/api/telegram/generate-link-code"),
        ("POST", "/api/telegram/unlink"),
        ("POST", "/api/telegram/webhook"),
    ], f"/api/telegram/* inventory drifted: {inventory}"


# ---------------------------------------------------------------------------
# 2. duplicate /auth/telegram-* surface is gone
# ---------------------------------------------------------------------------


def test_auth_telegram_routes_absent() -> None:
    """The duplicated /api/auth/telegram-link|disconnect routes are deleted."""
    paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/api/auth/telegram-link" not in paths
    assert "/api/auth/telegram-disconnect" not in paths


def test_old_telegram_link_response_unimportable() -> None:
    """TelegramLinkResponse (the old core schema) cannot be imported anymore."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.modules.core.schemas")


# ---------------------------------------------------------------------------
# 3. generate-link-code contract: typed response, no Russian `message`
# ---------------------------------------------------------------------------


def test_generate_link_code_response_model_is_typed() -> None:
    """The route declares TelegramLinkCodeResponse with code + bot_url only."""
    from app.modules.telegram.schemas import TelegramLinkCodeResponse

    fields = TelegramLinkCodeResponse.model_fields
    assert set(fields.keys()) == {"code", "bot_url"}, (
        f"generate-link-code response model drifted: {set(fields.keys())}"
    )

    route = next(
        r
        for r in app.routes
        if isinstance(r, APIRoute) and r.path == "/api/telegram/generate-link-code"
    )
    assert route.response_model is TelegramLinkCodeResponse


def test_generate_link_code_handler_flushes_and_uses_alnum_code() -> None:
    """Handler uses the 6-char ALNUM alphabet and awaits db.flush()."""
    from app.modules.telegram import api as telegram_api

    assert telegram_api.LINK_CODE_LENGTH == 6
    assert telegram_api.LINK_CODE_ALPHABET, (
        "LINK_CODE_ALPHABET must be a non-empty constant"
    )
    src = inspect.getsource(telegram_api.generate_link_code)
    assert "LINK_CODE_LENGTH" in src
    assert "LINK_CODE_ALPHABET" in src
    assert "await db.flush()" in src, (
        "generate_link_code must persist telegram_link_code via db.flush()"
    )
    assert "message" not in src, (
        "generate-link-code must not return the Russian `message` field"
    )


def test_unlink_and_status_responses_are_typed() -> None:
    """The remaining two routes also use typed Pydantic models."""
    from app.modules.telegram.schemas import (
        TelegramStatusResponse,
        TelegramUnlinkResponse,
    )

    routes = {
        r.path: r
        for r in app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/api/telegram/")
    }
    assert routes["/api/telegram/unlink"].response_model is TelegramUnlinkResponse
    assert routes["/api/telegram/status"].response_model is TelegramStatusResponse


# ---------------------------------------------------------------------------
# 4. no Russian inside telegram/ (replies live in English module constants)
# ---------------------------------------------------------------------------


_CYRILLIC = re.compile(r"[\u0400-\u04FF]")


def test_no_hardcoded_russian_in_telegram_module() -> None:
    """No Cyrillic codepoints survive in app/modules/telegram/*.py."""
    module_dir = Path(
        importlib.import_module("app.modules.telegram").__file__
    ).parent
    offenders: list[tuple[str, int, str]] = []
    for py_file in sorted(module_dir.glob("*.py")):
        for i, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), 1):
            if _CYRILLIC.search(line):
                offenders.append((py_file.name, i, line))
    assert not offenders, (
        "Russian strings must live behind named constants or i18n keys, not "
        "inline in telegram/*.py: " + repr(offenders[:5])
    )


def test_webhook_uses_named_constants_not_inline_strings() -> None:
    """Every webhook branch references the TG_* constants, not raw literals."""
    from app.modules.telegram import api as telegram_api

    src = inspect.getsource(telegram_api.telegram_webhook)
    for constant in (
        "TG_WELCOME",
        "TG_LINKED_FMT",
        "TG_NOT_LINKED",
        "TG_HELP",
        "TG_LINK_SUCCESS_FMT",
        "TG_BAD_CODE",
        "TG_UNKNOWN",
    ):
        assert constant in src, (
            f"webhook must reference {constant} instead of inline text"
        )


# ---------------------------------------------------------------------------
# 5. core/ is dissolved — only the admin cluster remains
# ---------------------------------------------------------------------------


def test_core_api_auth_and_schemas_deleted() -> None:
    """core/api_auth.py + core/schemas.py are gone; importing them raises."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.modules.core.api_auth")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.modules.core.schemas")


def test_core_api_telegram_legacy_path_unimportable() -> None:
    """The legacy app.modules.core.api_telegram path is gone after CORE-TG1."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.modules.core.api_telegram")


def test_core_admin_cluster_still_imports() -> None:
    """Phase 5 admin cluster (api_admin/admin_service/pool_maintenance) lives on."""
    for mod in (
        "app.modules.core.api_admin",
        "app.modules.core.admin_service",
        "app.modules.core.pool_maintenance",
    ):
        assert importlib.import_module(mod) is not None


def test_core_directory_only_holds_admin_phase5_residue() -> None:
    """No telegram/auth residue lingers under app/modules/core/."""
    core_dir = Path(
        importlib.import_module("app.modules.core").__file__
    ).parent
    actual = {p.name for p in core_dir.glob("*.py")}
    assert actual == {
        "__init__.py",
        "api_admin.py",
        "admin_service.py",
        "pool_maintenance.py",
    }, f"core/ residue drifted: {actual}"


# ---------------------------------------------------------------------------
# 6. main.py wiring
# ---------------------------------------------------------------------------


def test_main_imports_telegram_module_not_core() -> None:
    """main.py imports the telegram router from app.modules.telegram.api only."""
    main_src = inspect.getsource(importlib.import_module("app.main"))
    assert "from app.modules.telegram.api import router as telegram_router" in main_src
    assert "app.modules.core.api_telegram" not in main_src
    assert "app.modules.core.api_auth" not in main_src


# ---------------------------------------------------------------------------
# 7. telegram remains a consumer of alerts/notifications
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_replies_go_through_telegram_channel(monkeypatch) -> None:
    """The /start branch composes a NotificationMessage and hands it to
    TelegramChannel.send — confirming the channel-consumer relationship
    introduced in DA1 still holds after the move."""
    from app.modules.alerts.notifications import NotificationMessage
    from app.modules.telegram import api as telegram_api

    fake_send = AsyncMock(return_value=True)
    monkeypatch.setattr(telegram_api._telegram_channel, "send", fake_send)

    ok = await telegram_api._send_html(123, telegram_api.TG_WELCOME)
    assert ok is True
    fake_send.assert_awaited_once()
    args, _kwargs = fake_send.call_args
    assert args[0] == "123"
    assert isinstance(args[1], NotificationMessage)
    assert args[1].parse_mode == "HTML"
    assert args[1].body == telegram_api.TG_WELCOME
