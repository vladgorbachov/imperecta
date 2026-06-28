"""DB-free routing tests — ai_analyst chat write sites use CHAT door."""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.core import User
from app.modules.ai_analyst.service import chat

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _read_source(rel_path: str) -> str:
    return (BACKEND_ROOT / rel_path).read_text(encoding="utf-8")


def test_no_raw_chat_mutations_in_service() -> None:
    source = _read_source("app/modules/ai_analyst/service.py")
    for token in ("db.add(", "await db.flush()"):
        assert token not in source, f"service.py still contains raw mutation: {token}"


def test_service_imports_chat_gate() -> None:
    source = _read_source("app/modules/ai_analyst/service.py")
    assert "write_chat_async" in source
    assert "build_chat_session_fields" in source
    assert "build_chat_message_fields" in source


@pytest.mark.asyncio
@patch("app.modules.ai_analyst.service.write_chat_async", new_callable=AsyncMock)
@patch("app.modules.ai_analyst.service._get_client")
@patch("app.modules.ai_analyst.service.write_logs_async", new_callable=AsyncMock)
@patch("app.modules.ai_analyst.service.resolve_claude_model", new_callable=AsyncMock)
async def test_site_16_session_create_calls_gate(
    mock_model: AsyncMock,
    mock_logs: AsyncMock,
    mock_client_factory: MagicMock,
    mock_write: AsyncMock,
) -> None:
    mock_write.return_value = MagicMock(ok=True)
    mock_model.return_value = "claude-test"
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="assistant reply")]
    mock_response.usage = MagicMock(input_tokens=1, output_tokens=2)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    mock_client_factory.return_value = mock_client

    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    db = AsyncMock()
    db.execute = AsyncMock(return_value=execute_result)

    user = MagicMock(spec=User)
    user.id = uuid4()
    user.plan = "pro"

    await chat(db, user, session_id=None, message="Hello")

    assert mock_write.await_count == 3
    first = mock_write.await_args_list[0].kwargs
    assert first["table"] == "ai_chat_sessions"
    assert first["kind"] == "session_create"


@pytest.mark.asyncio
@patch("app.modules.ai_analyst.service.write_chat_async", new_callable=AsyncMock)
@patch("app.modules.ai_analyst.service._get_client")
@patch("app.modules.ai_analyst.service.write_logs_async", new_callable=AsyncMock)
@patch("app.modules.ai_analyst.service.resolve_claude_model", new_callable=AsyncMock)
async def test_site_17_user_message_calls_gate(
    mock_model: AsyncMock,
    mock_logs: AsyncMock,
    mock_client_factory: MagicMock,
    mock_write: AsyncMock,
) -> None:
    mock_write.return_value = MagicMock(ok=True)
    mock_model.return_value = "claude-test"
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="assistant reply")]
    mock_response.usage = MagicMock(input_tokens=1, output_tokens=2)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    mock_client_factory.return_value = mock_client

    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    db = AsyncMock()
    db.execute = AsyncMock(return_value=execute_result)

    user = MagicMock(spec=User)
    user.id = uuid4()
    user.plan = "pro"

    await chat(db, user, session_id=None, message="Hello")

    second = mock_write.await_args_list[1].kwargs
    assert second["table"] == "ai_chat_messages"
    assert second["kind"] == "message_append"
    assert second["fields"]["role"] == "user"


@pytest.mark.asyncio
@patch("app.modules.ai_analyst.service.write_chat_async", new_callable=AsyncMock)
@patch("app.modules.ai_analyst.service._get_client")
@patch("app.modules.ai_analyst.service.write_logs_async", new_callable=AsyncMock)
@patch("app.modules.ai_analyst.service.resolve_claude_model", new_callable=AsyncMock)
async def test_site_18_assistant_message_calls_gate(
    mock_model: AsyncMock,
    mock_logs: AsyncMock,
    mock_client_factory: MagicMock,
    mock_write: AsyncMock,
) -> None:
    mock_write.return_value = MagicMock(ok=True)
    mock_model.return_value = "claude-test"
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="assistant reply")]
    mock_response.usage = MagicMock(input_tokens=1, output_tokens=2)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    mock_client_factory.return_value = mock_client

    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    db = AsyncMock()
    db.execute = AsyncMock(return_value=execute_result)

    user = MagicMock(spec=User)
    user.id = uuid4()
    user.plan = "pro"

    await chat(db, user, session_id=None, message="Hello")

    third = mock_write.await_args_list[2].kwargs
    assert third["table"] == "ai_chat_messages"
    assert third["kind"] == "message_append"
    assert third["fields"]["role"] == "assistant"


def test_chat_service_avoids_orm_echo() -> None:
    source = inspect.getsource(chat)
    assert "db.add" not in source
    assert "db.flush" not in source
