"""DB-free routing tests — all 15 public.users write sites use USER door."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.entitlements.plan import UserPlan
from app.modules.auth.api import change_initial_password, login, register
from app.modules.auth.schemas import ChangeInitialPasswordRequest, UserLogin, UserRegister
from app.modules.core.admin_service import ensure_superuser
from app.modules.market_data.reader import MarketDataService
from app.modules.telegram.api import generate_link_code, telegram_webhook, unlink_telegram
from app.modules.users.service import UsersAdminService, UsersService

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _admin_detailed_row(user_id: UUID) -> dict:
    return {
        "id": user_id,
        "email": "x@y.com",
        "name": None,
        "company_name": None,
        "plan": "trial",
        "is_active": True,
        "is_superuser": False,
        "language": "en",
        "timezone": "UTC",
        "login_count": 0,
        "tracked_products": 0,
        "last_login_at": None,
        "created_at": None,
    }


def _admin_db_mock(*, user_id: UUID, is_superuser: bool = False, superuser_count: int = 2) -> AsyncMock:
    db = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock(is_superuser=is_superuser))
    db.scalar = AsyncMock(return_value=superuser_count)
    mapping_result = MagicMock()
    mapping_result.first.return_value = _admin_detailed_row(user_id)
    execute_result = MagicMock()
    execute_result.mappings.return_value = mapping_result
    db.execute = AsyncMock(return_value=execute_result)
    return db


def _read_source(rel_path: str) -> str:
    return (BACKEND_ROOT / rel_path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "rel_path,forbidden",
    [
        ("app/modules/auth/api.py", ("db.add(", "await db.flush()")),
        ("app/modules/users/service.py", ("db.add(", "setattr(current_user", "await self.db.commit()")),
        ("app/modules/core/admin_service.py", ("db.add(", "await db.commit()")),
        ("app/modules/telegram/api.py", ("user.telegram_chat_id =", "current_user.telegram_chat_id =", "await db.flush()")),
        ("app/modules/market_data/reader.py", ("user.preferences =", "await self.db.commit()")),
    ],
)
def test_no_raw_user_mutations_in_producer_modules(rel_path: str, forbidden: tuple[str, ...]) -> None:
    source = _read_source(rel_path)
    for token in forbidden:
        assert token not in source, f"{rel_path} still contains raw mutation: {token}"


def test_all_producer_modules_import_user_gate() -> None:
    for rel in (
        "app/modules/auth/api.py",
        "app/modules/users/service.py",
        "app/modules/core/admin_service.py",
        "app/modules/telegram/api.py",
        "app/modules/market_data/reader.py",
    ):
        source = _read_source(rel)
        assert "write_user_async" in source or "write_user_sync" in source
        assert "build_user_fields" in source


@pytest.mark.asyncio
@patch("app.modules.auth.api.hash_password", return_value="hashed")
@patch("app.modules.auth.api.write_user_async", new_callable=AsyncMock)
async def test_site_1_register_calls_gate(mock_write: AsyncMock, _mock_hash: MagicMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    db.execute.return_value = execute_result
    data = UserRegister(
        email="a@b.com",
        password="secret12",
        name="A",
        company_name=None,
        language="en",
    )
    await register(data, db)
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["operation"] == "insert"
    assert mock_write.call_args.kwargs["kind"] == "register"


@pytest.mark.asyncio
@patch("app.modules.auth.api.write_user_async", new_callable=AsyncMock)
async def test_site_2_login_calls_gate(mock_write: AsyncMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    user = MagicMock()
    user.id = uuid4()
    user.force_password_change = False
    user.password_hash = "x"
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = user
    db.execute.return_value = execute_result
    with patch("app.modules.auth.api.verify_password", return_value=True):
        await login(UserLogin(email="a@b.com", password="p"), db)
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["kind"] == "login_touch"


@pytest.mark.asyncio
@patch("app.modules.auth.api.hash_password", return_value="hashed")
@patch("app.modules.auth.api.write_user_async", new_callable=AsyncMock)
async def test_site_3_password_change_calls_gate(mock_write: AsyncMock, _mock_hash: MagicMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    current_user = MagicMock()
    current_user.id = uuid4()
    current_user.force_password_change = True
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    db.execute.return_value = execute_result
    data = ChangeInitialPasswordRequest(
        new_email="new@b.com",
        new_password="newsecret12",
    )
    await change_initial_password(data, current_user, db)
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["kind"] == "password_change"


@pytest.mark.asyncio
@patch("app.modules.users.service.write_user_async", new_callable=AsyncMock)
async def test_site_4_self_update_calls_gate(mock_write: AsyncMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    user = MagicMock()
    user.id = uuid4()
    user.email = "u@x.com"
    user.name = "Old"
    user.company_name = None
    user.plan = "trial"
    user.trial_ends_at = None
    user.language = "en"
    user.timezone = "UTC"
    user.ai_tone = "balanced"
    user.default_currency = "EUR"
    user.is_superuser = False
    user.is_active = True
    user.created_at = datetime.now(tz=timezone.utc)
    user.last_login_at = None
    user.telegram_chat_id = None
    user.avatar_url = None
    user.preferences = {}
    db = AsyncMock()
    db.refresh = AsyncMock()
    svc = UsersService(db)
    await svc.update_me(user, {"name": "New"})
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["kind"] == "self_update"


@pytest.mark.asyncio
@patch("app.modules.users.service.hash_password", return_value="hashed")
@patch("app.modules.users.service.write_user_async", new_callable=AsyncMock)
async def test_site_5_admin_create_calls_gate(mock_write: AsyncMock, _mock_hash: MagicMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    user_id = uuid4()
    db = _admin_db_mock(user_id=user_id)
    db.scalar = AsyncMock(return_value=None)
    svc = UsersAdminService(db)
    await svc.create_user(
        email="x@y.com",
        password="secret12",
        name=None,
        company_name=None,
        plan="trial",
        language="en",
        timezone="UTC",
        is_active=True,
        is_superuser=False,
    )
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["kind"] == "admin_create"


@pytest.mark.asyncio
@patch("app.modules.users.service.write_user_async", new_callable=AsyncMock)
async def test_site_6_admin_update_calls_gate(mock_write: AsyncMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    user_id = uuid4()
    db = _admin_db_mock(user_id=user_id)
    svc = UsersAdminService(db)
    await svc.update_user(user_id, name="N")
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["kind"] == "admin_update"


@pytest.mark.asyncio
@patch("app.modules.users.service.write_user_async", new_callable=AsyncMock)
async def test_site_7_admin_active_calls_gate(mock_write: AsyncMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    user_id = uuid4()
    actor = uuid4()
    db = _admin_db_mock(user_id=user_id, is_superuser=False)
    svc = UsersAdminService(db)
    await svc.set_user_active(user_id, is_active=False, actor_user_id=actor)
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["kind"] == "admin_update"


@pytest.mark.asyncio
@patch("app.modules.users.service.write_user_async", new_callable=AsyncMock)
async def test_site_8_admin_superuser_calls_gate(mock_write: AsyncMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    user_id = uuid4()
    actor = uuid4()
    db = _admin_db_mock(user_id=user_id, is_superuser=True)
    svc = UsersAdminService(db)
    await svc.set_user_superuser(user_id, is_superuser=True, actor_user_id=actor)
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["kind"] == "admin_update"


@pytest.mark.asyncio
@patch("app.modules.users.service.hash_password", return_value="hashed")
@patch("app.modules.users.service.write_user_async", new_callable=AsyncMock)
async def test_site_9_admin_password_reset_calls_gate(mock_write: AsyncMock, _mock_hash: MagicMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    user_id = uuid4()
    db = _admin_db_mock(user_id=user_id)
    svc = UsersAdminService(db)
    await svc.reset_user_password(
        user_id,
        new_password="secret12",
        force_password_change=True,
    )
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["kind"] == "admin_password_reset"


@pytest.mark.asyncio
@patch("app.modules.users.service.write_user_async", new_callable=AsyncMock)
async def test_site_10_admin_delete_calls_gate(mock_write: AsyncMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    user_id = uuid4()
    actor = uuid4()
    db = _admin_db_mock(user_id=user_id, is_superuser=False)
    svc = UsersAdminService(db)
    await svc.delete_user(user_id, actor_user_id=actor)
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["operation"] == "delete"
    assert mock_write.call_args.kwargs["kind"] == "admin_delete"


@pytest.mark.asyncio
@patch("app.modules.core.admin_service.hash_password", return_value="hashed")
@patch("app.modules.core.admin_service.write_user_sync")
@patch("app.modules.core.admin_service.asyncio.to_thread", new_callable=AsyncMock)
async def test_site_11_bootstrap_calls_gate(
    mock_to_thread: AsyncMock,
    mock_write: MagicMock,
    _mock_hash: MagicMock,
) -> None:
    async def _run_sync(fn, **kwargs):
        return fn(**kwargs)

    mock_to_thread.side_effect = _run_sync
    mock_write.return_value = MagicMock(ok=True)
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=execute_result)
    with patch("app.modules.core.admin_service.Settings") as mock_settings:
        mock_settings.return_value.bootstrap_admin_email = "admin@x.com"
        mock_settings.return_value.bootstrap_admin_password = "secret12"
        mock_settings.return_value.bootstrap_admin_name = "Admin"
        mock_settings.return_value.bootstrap_admin_language = "en"
        mock_settings.return_value.bootstrap_admin_plan = UserPlan.enterprise.value
        await ensure_superuser(db)
    mock_write.assert_called_once()
    assert mock_write.call_args.kwargs["kind"] == "admin_create"


@pytest.mark.asyncio
@patch("app.modules.telegram.api.write_user_async", new_callable=AsyncMock)
async def test_site_12_webhook_link_calls_gate(mock_write: AsyncMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    user = MagicMock()
    user.id = uuid4()
    user.email = "u@x.com"
    db = AsyncMock()
    link_result = MagicMock()
    link_result.scalar_one_or_none.return_value = user
    db.execute.return_value = link_result
    request = MagicMock()
    request.headers.get.return_value = "secret"
    request.json = AsyncMock(return_value={"message": {"text": "ABC123", "chat": {"id": 99}}})
    with patch("app.modules.telegram.api._verify_telegram_webhook_secret", return_value=True), patch(
        "app.modules.telegram.api._send_html",
        new_callable=AsyncMock,
    ):
        await telegram_webhook(request, db)
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["kind"] == "telegram_link"


@pytest.mark.asyncio
@patch("app.modules.telegram.api.write_user_async", new_callable=AsyncMock)
async def test_site_13_generate_link_code_calls_gate(mock_write: AsyncMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    current_user = MagicMock()
    current_user.id = uuid4()
    await generate_link_code(current_user, AsyncMock())
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["kind"] == "telegram_link"


@pytest.mark.asyncio
@patch("app.modules.telegram.api.write_user_async", new_callable=AsyncMock)
async def test_site_14_unlink_calls_gate(mock_write: AsyncMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    current_user = MagicMock()
    current_user.id = uuid4()
    current_user.telegram_chat_id = 123
    await unlink_telegram(current_user, AsyncMock())
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["kind"] == "telegram_link"


@pytest.mark.asyncio
@patch("app.modules.market_data.reader.write_user_async", new_callable=AsyncMock)
async def test_site_15_preferences_calls_gate(mock_write: AsyncMock) -> None:
    mock_write.return_value = MagicMock(ok=True)
    user = MagicMock()
    user.id = uuid4()
    user.preferences = {}
    db = AsyncMock()
    svc = MarketDataService(db)
    await svc.update_preferences(user, {"forex_favorites": ["EUR"]})
    mock_write.assert_awaited_once()
    assert mock_write.call_args.kwargs["kind"] == "self_update"


def test_bootstrap_uses_import_safe_sync_gate() -> None:
    """Gate modules are import-safe at lifespan (no DB at import time)."""
    source = inspect.getsource(ensure_superuser)
    assert "write_user_sync" in source
    assert "db.add" not in source
