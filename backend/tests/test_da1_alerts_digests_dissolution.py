"""
DA1 dissolution + notifications tests.

Framework-light invariants (no DB / no HTTP for the structural checks) that
prove:

1. Both `app.modules.alerts.{api,service,schemas,tasks,models}` and
   `app.modules.digests.{api,service,tasks,schemas,models}` no longer import.
2. The 7 previously-stub `/api/alerts/*` paths and the 2 `/api/digests` paths
   are gone from the live FastAPI app.
3. Celery `conf.include` no longer references the deleted task modules.
4. The new `alerts.notifications` submodule exposes a clean channel
   contract (`NotificationChannel`, `NotificationMessage`) plus working
   `TelegramChannel` and `EmailChannel` strategies.
5. The channel core is universal: no hardcoded currency, no hardcoded
   Russian copy, no `asyncio.run` antipattern anywhere under
   `backend/app/modules/alerts/`.
6. None of the legacy notification helpers (`send_message`,
   `send_price_alert`, `send_alert_email_to_user`, etc.) survive in the
   backend source tree outside this test file.
"""

import importlib
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.main import app
from app.modules.alerts.notifications import (
    EmailChannel,
    NotificationChannel,
    NotificationMessage,
    TelegramChannel,
)
from app.workers.celery_app import celery_app

ALERTS_DELETED_PATHS: set[str] = {
    "/api/alerts/",
    "/api/alerts/{id}",
    "/api/alerts/events",
    "/api/alerts/events/{event_id}/explanation",
    "/api/alerts/events/{event_id}/auto-response",
}

DIGESTS_DELETED_PATHS: set[str] = {
    "/api/digests",
    "/api/digests/{id}",
}

DELETED_TASK_INCLUDES: set[str] = {
    "app.modules.alerts.tasks",
    "app.modules.digests.tasks",
}

FORBIDDEN_LEGACY_SYMBOLS: tuple[str, ...] = (
    "send_price_alert",
    "send_out_of_stock_alert",
    "send_promo_alert",
    "send_digest",
    "send_alert_email_to_user",
    "send_digest_email_to_user",
    "check_alerts",
    "generate_alert_ai_explanation",
    "generate_alert_explanation",
    "generate_auto_response",
)

FORBIDDEN_BUSINESS_LITERALS: tuple[str, ...] = (
    '"RUB"',
    "Изменение цены",
    "Нет в наличии",
    "asyncio.run",
)

ALERTS_MODULE_DIR = (
    Path(__file__).resolve().parents[1] / "app" / "modules" / "alerts"
)
BACKEND_APP_DIR = Path(__file__).resolve().parents[1] / "app"


# ---------------------------------------------------------------------------
# 1. Module dissolution
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_path",
    [
        "app.modules.alerts.api",
        "app.modules.alerts.service",
        "app.modules.alerts.schemas",
        "app.modules.alerts.tasks",
        "app.modules.alerts.models",
        "app.modules.digests.api",
        "app.modules.digests.service",
        "app.modules.digests.tasks",
        "app.modules.digests.schemas",
        "app.modules.digests.models",
    ],
)
def test_deleted_submodules_no_longer_import(module_path: str) -> None:
    with pytest.raises(ImportError):
        importlib.import_module(module_path)


def test_alerts_package_still_imports_for_notifications() -> None:
    """The `alerts` package itself remains - it now hosts only `notifications`."""
    importlib.import_module("app.modules.alerts")
    importlib.import_module("app.modules.alerts.notifications")


def test_digests_package_is_bare_skeleton() -> None:
    """The `digests` package imports cleanly with no submodules."""
    pkg = importlib.import_module("app.modules.digests")
    assert pkg.__doc__ and "DA1" in pkg.__doc__, (
        "DA1 expects digests package to be a documented empty skeleton"
    )


# ---------------------------------------------------------------------------
# 2. Routes are unmounted from the live app
# ---------------------------------------------------------------------------


def test_no_alerts_routes_mounted() -> None:
    actual_paths = {getattr(route, "path", None) for route in app.routes}
    leftover_alerts = {p for p in actual_paths if p and p.startswith("/api/alerts")}
    assert not leftover_alerts, (
        f"DA1 deletion failed - alerts routes still mounted: {sorted(leftover_alerts)}"
    )
    still_present = ALERTS_DELETED_PATHS & actual_paths
    assert not still_present, (
        f"Specific deleted alerts paths still mounted: {sorted(still_present)}"
    )


def test_no_digests_routes_mounted() -> None:
    actual_paths = {getattr(route, "path", None) for route in app.routes}
    leftover_digests = {p for p in actual_paths if p and p.startswith("/api/digests")}
    assert not leftover_digests, (
        f"DA1 deletion failed - digests routes still mounted: {sorted(leftover_digests)}"
    )
    still_present = DIGESTS_DELETED_PATHS & actual_paths
    assert not still_present, (
        f"Specific deleted digests paths still mounted: {sorted(still_present)}"
    )


# ---------------------------------------------------------------------------
# 3. Celery include is clean
# ---------------------------------------------------------------------------


def test_celery_include_drops_alerts_and_digests_task_modules() -> None:
    include = set(celery_app.conf.include)
    overlap = include & DELETED_TASK_INCLUDES
    assert not overlap, (
        f"celery_app.conf.include still references deleted task modules: {sorted(overlap)}"
    )


def test_celery_app_imports_without_error() -> None:
    """Re-importing celery_app succeeds (proves include resolves)."""
    importlib.import_module("app.workers.celery_app")


# ---------------------------------------------------------------------------
# 4. Notification channel contract + strategies
# ---------------------------------------------------------------------------


def test_channel_contract_is_abstract() -> None:
    with pytest.raises(TypeError):
        NotificationChannel()  # type: ignore[abstract]
    assert issubclass(TelegramChannel, NotificationChannel)
    assert issubclass(EmailChannel, NotificationChannel)


def test_notification_message_is_universal() -> None:
    """The DTO carries body + optional title/parse_mode and is frozen."""
    msg = NotificationMessage(body="hello", title="hi", parse_mode="HTML")
    assert msg.body == "hello"
    assert msg.title == "hi"
    assert msg.parse_mode == "HTML"
    with pytest.raises(Exception):
        msg.body = "mutated"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_telegram_channel_returns_false_when_token_unset() -> None:
    fake_settings = SimpleNamespace(telegram_bot_token=None)
    with patch("app.modules.alerts.notifications.telegram.settings", fake_settings):
        channel = TelegramChannel()
        ok = await channel.send("123", NotificationMessage(body="hi"))
    assert ok is False


@pytest.mark.asyncio
async def test_telegram_channel_calls_send_message_with_payload() -> None:
    captured: dict[str, object] = {}

    class _StubResponse:
        status_code = 200
        text = ""

    async def _stub_post(self, url: str, json: dict) -> _StubResponse:
        captured["url"] = url
        captured["json"] = json
        return _StubResponse()

    fake_settings = SimpleNamespace(telegram_bot_token="TOKEN-XYZ")
    with patch(
        "app.modules.alerts.notifications.telegram.settings", fake_settings
    ), patch.object(httpx.AsyncClient, "post", _stub_post):
        channel = TelegramChannel()
        ok = await channel.send(
            "555",
            NotificationMessage(body="hello world", parse_mode="HTML"),
        )

    assert ok is True
    assert captured["url"] == "https://api.telegram.org/botTOKEN-XYZ/sendMessage"
    assert captured["json"] == {
        "chat_id": 555,
        "text": "hello world",
        "parse_mode": "HTML",
    }


@pytest.mark.asyncio
async def test_telegram_channel_returns_false_for_non_numeric_recipient() -> None:
    fake_settings = SimpleNamespace(telegram_bot_token="TOKEN")
    with patch("app.modules.alerts.notifications.telegram.settings", fake_settings):
        channel = TelegramChannel()
        ok = await channel.send("not-an-int", NotificationMessage(body="x"))
    assert ok is False


@pytest.mark.asyncio
async def test_telegram_channel_returns_false_on_non_200() -> None:
    class _StubResponse:
        status_code = 429
        text = "Too many requests"

    async def _stub_post(self, url: str, json: dict) -> _StubResponse:
        return _StubResponse()

    fake_settings = SimpleNamespace(telegram_bot_token="TOKEN")
    with patch(
        "app.modules.alerts.notifications.telegram.settings", fake_settings
    ), patch.object(httpx.AsyncClient, "post", _stub_post):
        channel = TelegramChannel()
        ok = await channel.send("1", NotificationMessage(body="x"))
    assert ok is False


@pytest.mark.asyncio
async def test_email_channel_returns_false_when_api_key_unset() -> None:
    fake_settings = SimpleNamespace(resend_api_key=None, email_from="noreply@x.io")
    with patch("app.modules.alerts.notifications.email.settings", fake_settings):
        channel = EmailChannel()
        ok = await channel.send(
            "user@example.com",
            NotificationMessage(body="<p>hi</p>", title="Subject"),
        )
    assert ok is False


@pytest.mark.asyncio
async def test_email_channel_requires_subject() -> None:
    fake_settings = SimpleNamespace(resend_api_key="re_KEY", email_from="noreply@x.io")
    with patch("app.modules.alerts.notifications.email.settings", fake_settings):
        channel = EmailChannel()
        ok = await channel.send(
            "user@example.com",
            NotificationMessage(body="<p>hi</p>"),
        )
    assert ok is False


@pytest.mark.asyncio
async def test_email_channel_calls_resend_with_payload() -> None:
    fake_settings = SimpleNamespace(resend_api_key="re_KEY", email_from="bot@x.io")
    fake_emails = MagicMock()
    fake_resend = SimpleNamespace(
        api_key=None,
        Emails=SimpleNamespace(send=fake_emails.send),
    )
    with patch(
        "app.modules.alerts.notifications.email.settings", fake_settings
    ), patch("app.modules.alerts.notifications.email.resend", fake_resend):
        channel = EmailChannel()
        ok = await channel.send(
            "user@example.com",
            NotificationMessage(body="<p>hi</p>", title="Subject"),
        )

    assert ok is True
    assert fake_resend.api_key == "re_KEY"
    fake_emails.send.assert_called_once_with(
        {
            "from": "bot@x.io",
            "to": ["user@example.com"],
            "subject": "Subject",
            "html": "<p>hi</p>",
        }
    )


# ---------------------------------------------------------------------------
# 5. Source scan: notifications core stays universal + clean
# ---------------------------------------------------------------------------


def test_alerts_module_has_no_business_literals_or_antipatterns() -> None:
    """No RUB / Russian alert copy / asyncio.run inside the rebuilt alerts/."""
    offenders: list[tuple[str, str]] = []
    for path in ALERTS_MODULE_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_BUSINESS_LITERALS:
            if needle in text:
                offenders.append((str(path.relative_to(ALERTS_MODULE_DIR)), needle))
    assert not offenders, (
        "Notification core must stay universal (no hardcoded currency / "
        "language / asyncio.run). Offenders:\n"
        + "\n".join(f"  {p}: {needle}" for p, needle in offenders)
    )


def test_no_legacy_notification_helpers_in_backend_source() -> None:
    """The old `send_*` / `check_alerts` / `generate_alert_*` helpers are gone everywhere."""
    self_path = Path(__file__).resolve()
    offenders: list[tuple[str, str]] = []
    for path in BACKEND_APP_DIR.rglob("*.py"):
        if path.resolve() == self_path:
            continue
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_LEGACY_SYMBOLS:
            if needle in text:
                offenders.append((str(path.relative_to(BACKEND_APP_DIR)), needle))
    assert not offenders, (
        "Legacy notification helpers must be deleted from backend/app:\n"
        + "\n".join(f"  {p}: {needle}" for p, needle in offenders)
    )


def test_telegram_channel_send_signature_matches_contract() -> None:
    """Both concrete channels share the abstract `send(recipient, message)` contract."""
    for cls in (TelegramChannel, EmailChannel):
        sig = inspect.signature(cls.send)
        params = list(sig.parameters.values())
        assert [p.name for p in params] == ["self", "recipient", "message"], (
            f"{cls.__name__}.send must keep the (self, recipient, message) contract"
        )


# ---------------------------------------------------------------------------
# 6. api_telegram still works after migration to TelegramChannel
# ---------------------------------------------------------------------------


def test_api_telegram_uses_new_channel_not_legacy_helper() -> None:
    """The Telegram bot integration now consumes notifications.TelegramChannel.

    CORE-TG1 moved the integration to ``app.modules.telegram.api`` (the
    last ``core`` resident was dissolved); the DA1 channel contract is
    unchanged.
    """
    api_telegram = importlib.import_module("app.modules.telegram.api")
    src = inspect.getsource(api_telegram)
    assert "TelegramChannel" in src
    assert "NotificationMessage" in src
    assert "send_message" not in src, (
        "telegram/api.py must not reference the deleted send_message helper"
    )


def test_telegram_module_uses_settings_directly_for_bot_url() -> None:
    """``BOT_URL`` constant is gone; telegram/api reads ``telegram_bot_url``
    from Settings (CORE-TG1: the residual ``core/api_auth.py`` was deleted)."""
    telegram_api = importlib.import_module("app.modules.telegram.api")
    src = inspect.getsource(telegram_api)
    assert "BOT_URL" not in src
    assert "telegram_bot_url" in src


# ---------------------------------------------------------------------------
# 7. Smoke: TelegramChannel can be awaited via AsyncMock-style stubs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telegram_channel_supports_dependency_injection_via_send() -> None:
    """Callers can replace the channel with an AsyncMock for unit tests."""
    fake_channel = AsyncMock(spec=NotificationChannel)
    fake_channel.send.return_value = True

    ok = await fake_channel.send(
        "999",
        NotificationMessage(body="payload", parse_mode="HTML"),
    )
    assert ok is True
    fake_channel.send.assert_awaited_once()
