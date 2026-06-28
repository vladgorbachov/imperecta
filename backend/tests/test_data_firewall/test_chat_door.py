"""Pure-logic tests for CHAT door (ai_chat_* owner-scope gate)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.chat_door import (
    REJECT_COLUMN_NOT_ALLOWED,
    REJECT_INVALID_MESSAGE_ROLE,
    REJECT_OWNER_MISSING,
    authorize_chat_write,
)
from app.modules.data_firewall.contracts import FACT_TABLE_CONTRACTS, TABLE_LOCATORS
from app.modules.data_firewall.signing import reset_signing_settings_cache, sign, verify
from app.modules.persist.chat_write import (
    build_chat_message_fields,
    build_chat_session_fields,
    write_chat_sync,
)


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def test_chat_tables_registered() -> None:
    assert "ai_chat_sessions" in FACT_TABLE_CONTRACTS
    assert "ai_chat_messages" in FACT_TABLE_CONTRACTS
    assert TABLE_LOCATORS["ai_chat_sessions"] == ("id",)
    assert TABLE_LOCATORS["ai_chat_messages"] == ("id",)


def test_session_create_requires_user_id() -> None:
    session_id = uuid4()
    fields = build_chat_session_fields(
        id=session_id,
        title="Hello",
        context_type="general",
    )
    outcome = authorize_chat_write(
        fields,
        operation="insert",
        table="ai_chat_sessions",
        kind="session_create",
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == REJECT_OWNER_MISSING


def test_session_create_passes_with_user_id() -> None:
    session_id = uuid4()
    user_id = uuid4()
    fields = build_chat_session_fields(
        id=session_id,
        user_id=user_id,
        title="Hello",
        context_type="general",
    )
    outcome = authorize_chat_write(
        fields,
        operation="insert",
        table="ai_chat_sessions",
        kind="session_create",
        db=MagicMock(),
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    assert outcome.signed_record.locator == {"id": str(session_id)}


def test_message_append_requires_session_id() -> None:
    fields = {"id": 1, "role": "user", "content": "hi"}
    outcome = authorize_chat_write(
        fields,
        operation="insert",
        table="ai_chat_messages",
        kind="message_append",
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == REJECT_OWNER_MISSING


def test_message_append_rejects_null_session_id() -> None:
    fields = {"id": 1, "session_id": None, "role": "user", "content": "hi"}
    outcome = authorize_chat_write(
        fields,
        operation="insert",
        table="ai_chat_messages",
        kind="message_append",
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == REJECT_OWNER_MISSING


def test_message_append_passes_with_session_id() -> None:
    session_id = uuid4()
    fields = build_chat_message_fields(
        id=42,
        session_id=session_id,
        role="assistant",
        content="reply",
    )
    outcome = authorize_chat_write(
        fields,
        operation="insert",
        table="ai_chat_messages",
        kind="message_append",
        db=MagicMock(),
    )
    assert outcome.passed is True


def test_message_append_rejects_invalid_role() -> None:
    session_id = uuid4()
    fields = build_chat_message_fields(
        id=7,
        session_id=session_id,
        role="system",
        content="x",
    )
    outcome = authorize_chat_write(
        fields,
        operation="insert",
        table="ai_chat_messages",
        kind="message_append",
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == REJECT_INVALID_MESSAGE_ROLE


def test_message_append_rejects_column_outside_allowlist() -> None:
    session_id = uuid4()
    fields = build_chat_message_fields(
        id=8,
        session_id=session_id,
        role="user",
        content="x",
        user_id=str(uuid4()),
    )
    outcome = authorize_chat_write(
        fields,
        operation="insert",
        table="ai_chat_messages",
        kind="message_append",
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == f"{REJECT_COLUMN_NOT_ALLOWED}:user_id"


def test_chat_signing_tamper_fails_verify() -> None:
    session_id = uuid4()
    fields = build_chat_session_fields(
        id=session_id,
        user_id=uuid4(),
        title="t",
        context_type="general",
    )
    outcome = authorize_chat_write(
        fields,
        operation="insert",
        table="ai_chat_sessions",
        kind="session_create",
        db=MagicMock(),
    )
    assert outcome.signed_record is not None
    locator = outcome.signed_record.locator
    signature = sign(
        table="ai_chat_sessions",
        operation="insert",
        fields=fields,
        locator=locator,
    )
    assert signature is not None
    assert not verify(
        table="ai_chat_sessions",
        operation="update",
        fields=fields,
        locator=locator,
        signature=signature,
    )


@patch("app.modules.persist.chat_write.write_sync")
@patch("app.modules.persist.chat_write.authorize_chat_write")
def test_write_chat_sync_rejects_on_gate_failure(
    mock_authorize: MagicMock,
    mock_write_sync: MagicMock,
) -> None:
    from app.modules.data_firewall.firewall import FirewallOutcome

    mock_authorize.return_value = FirewallOutcome(
        passed=False,
        reject_reason="test",
        failed_rules=["test"],
        forced_log_status=None,
        page_role_verdict=None,
        signed_record=None,
    )
    result = write_chat_sync(
        table="ai_chat_sessions",
        operation="insert",
        kind="session_create",
        fields=build_chat_session_fields(id=uuid4(), user_id=uuid4(), context_type="general"),
        reject_source="test",
    )
    assert result.ok is False
    mock_write_sync.assert_not_called()
