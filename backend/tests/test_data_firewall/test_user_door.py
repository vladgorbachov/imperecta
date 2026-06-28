"""Pure-logic tests for USER door (public.users full-lock gate)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.contracts import FACT_TABLE_CONTRACTS, TABLE_LOCATORS
from app.modules.data_firewall.signing import reset_signing_settings_cache, sign, verify
from app.modules.data_firewall.user_door import (
    REJECT_COLUMN_NOT_ALLOWED,
    REJECT_IS_ACTIVE_FORBIDDEN,
    REJECT_PASSWORD_HASH_FORBIDDEN,
    REJECT_PRIVILEGE_ESCALATION,
    REJECT_REACTIVATION_FORBIDDEN,
    USER_INSERT_ALLOWLIST,
    USER_UPDATE_ALLOWLIST,
    authorize_user_write,
)
from app.modules.data_firewall.user_active_predicate import may_set_active
from app.modules.data_firewall.user_superuser_predicate import may_set_superuser
from app.modules.persist.user_write import build_user_fields, write_user_sync


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def test_users_registered_in_contract_maps() -> None:
    assert "users" in FACT_TABLE_CONTRACTS
    assert TABLE_LOCATORS["users"] == ("id",)
    assert "register" in USER_INSERT_ALLOWLIST
    assert "admin_create" in USER_INSERT_ALLOWLIST
    assert "self_update" in USER_UPDATE_ALLOWLIST
    assert "admin_password_reset" in USER_UPDATE_ALLOWLIST


def test_may_set_active_reactivation_abolished() -> None:
    assert may_set_active(kind="admin_update", target_fields={"is_active": True}) is False
    assert may_set_active(kind="admin_create", target_fields={"is_active": True}) is False
    assert may_set_active(kind="admin_update", target_fields={"is_active": False}) is True
    assert may_set_active(kind="self_update", target_fields={"is_active": False}) is False
    assert may_set_active(kind="admin_update", target_fields={}) is True


def test_admin_create_allowlist_omits_is_active() -> None:
    assert "is_active" not in USER_INSERT_ALLOWLIST["admin_create"]


def test_may_set_superuser_admin_kinds_only() -> None:
    assert may_set_superuser(kind="admin_create", target_fields={"is_superuser": True}) is True
    assert may_set_superuser(kind="admin_update", target_fields={"is_superuser": False}) is True
    assert may_set_superuser(kind="register", target_fields={"is_superuser": True}) is False
    assert may_set_superuser(kind="self_update", target_fields={"is_superuser": False}) is False
    assert may_set_superuser(kind="login_touch", target_fields={"is_superuser": True}) is False


def test_self_update_escalation_uses_predicate() -> None:
    user_id = uuid4()
    fields = build_user_fields(id=user_id, is_superuser=True)
    with patch(
        "app.modules.data_firewall.user_door.may_set_superuser",
        return_value=False,
    ) as mock_predicate:
        outcome = authorize_user_write(
            fields,
            operation="update",
            kind="admin_update",
            db=MagicMock(),
        )
    mock_predicate.assert_called_once_with(kind="admin_update", target_fields=fields)
    assert outcome.passed is False
    assert outcome.reject_reason == REJECT_PRIVILEGE_ESCALATION


def test_register_insert_passes_and_signs() -> None:
    user_id = uuid4()
    fields = build_user_fields(
        id=user_id,
        email="new@example.com",
        password_hash="hashed",
        name="New",
        company_name="Co",
        plan="trial",
        trial_ends_at=datetime.now(tz=timezone.utc),
        language="en",
    )
    outcome = authorize_user_write(
        fields,
        operation="insert",
        kind="register",
        db=MagicMock(),
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    assert outcome.signed_record.operation == "insert"
    assert outcome.signed_record.locator == {"id": str(user_id)}


def test_self_update_rejects_is_superuser_true() -> None:
    user_id = uuid4()
    fields = build_user_fields(id=user_id, name="x", is_superuser=True)
    outcome = authorize_user_write(
        fields,
        operation="update",
        kind="self_update",
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == f"{REJECT_COLUMN_NOT_ALLOWED}:is_superuser"


def test_self_update_rejects_password_hash() -> None:
    user_id = uuid4()
    fields = build_user_fields(id=user_id, password_hash="hack")
    outcome = authorize_user_write(
        fields,
        operation="update",
        kind="self_update",
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == f"{REJECT_COLUMN_NOT_ALLOWED}:password_hash"


def test_login_touch_rejects_password_hash() -> None:
    user_id = uuid4()
    fields = build_user_fields(
        id=user_id,
        last_login_at=datetime.now(tz=timezone.utc),
        password_hash="hack",
    )
    outcome = authorize_user_write(
        fields,
        operation="update",
        kind="login_touch",
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert REJECT_COLUMN_NOT_ALLOWED in (outcome.reject_reason or "")


def test_admin_create_allows_is_superuser_without_is_active() -> None:
    user_id = uuid4()
    fields = build_user_fields(
        id=user_id,
        email="admin@example.com",
        password_hash="hashed",
        plan="enterprise",
        language="en",
        timezone="UTC",
        is_superuser=True,
    )
    outcome = authorize_user_write(
        fields,
        operation="insert",
        kind="admin_create",
        db=MagicMock(),
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    assert "is_active" not in outcome.signed_record.fields


def test_admin_update_rejects_is_active_reactivation() -> None:
    user_id = uuid4()
    fields = build_user_fields(id=user_id, is_active=True)
    outcome = authorize_user_write(
        fields,
        operation="update",
        kind="admin_update",
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == REJECT_REACTIVATION_FORBIDDEN


def test_admin_create_rejects_signed_is_active_true() -> None:
    user_id = uuid4()
    fields = build_user_fields(
        id=user_id,
        email="admin@example.com",
        password_hash="hashed",
        plan="enterprise",
        language="en",
        timezone="UTC",
        is_active=True,
    )
    outcome = authorize_user_write(
        fields,
        operation="insert",
        kind="admin_create",
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == f"{REJECT_COLUMN_NOT_ALLOWED}:is_active"


def test_admin_update_allows_deactivation() -> None:
    user_id = uuid4()
    fields = build_user_fields(id=user_id, is_active=False)
    outcome = authorize_user_write(
        fields,
        operation="update",
        kind="admin_update",
        db=MagicMock(),
    )
    assert outcome.passed is True


def test_self_update_rejects_is_active() -> None:
    user_id = uuid4()
    fields = build_user_fields(id=user_id, is_active=False)
    outcome = authorize_user_write(
        fields,
        operation="update",
        kind="self_update",
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == f"{REJECT_COLUMN_NOT_ALLOWED}:is_active"


def test_telegram_link_rejects_plan() -> None:
    user_id = uuid4()
    fields = build_user_fields(id=user_id, telegram_link_code="ABC123", plan="pro")
    outcome = authorize_user_write(
        fields,
        operation="update",
        kind="telegram_link",
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == f"{REJECT_COLUMN_NOT_ALLOWED}:plan"


def test_password_change_allows_password_hash() -> None:
    user_id = uuid4()
    fields = build_user_fields(
        id=user_id,
        email="u@example.com",
        password_hash="newhash",
        force_password_change=False,
    )
    outcome = authorize_user_write(
        fields,
        operation="update",
        kind="password_change",
        db=MagicMock(),
    )
    assert outcome.passed is True


def test_admin_password_reset_rejects_plan() -> None:
    user_id = uuid4()
    fields = build_user_fields(
        id=user_id,
        password_hash="x",
        force_password_change=True,
        plan="trial",
    )
    outcome = authorize_user_write(
        fields,
        operation="update",
        kind="admin_password_reset",
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == f"{REJECT_COLUMN_NOT_ALLOWED}:plan"


def test_admin_delete_locator_only() -> None:
    user_id = uuid4()
    fields = build_user_fields(id=user_id)
    outcome = authorize_user_write(
        fields,
        operation="delete",
        kind="admin_delete",
        db=MagicMock(),
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    assert outcome.signed_record.operation == "delete"


def test_tamper_operation_fails_verify() -> None:
    user_id = uuid4()
    fields = build_user_fields(id=user_id, last_login_at=datetime.now(tz=timezone.utc))
    outcome = authorize_user_write(
        fields,
        operation="update",
        kind="login_touch",
        db=MagicMock(),
    )
    assert outcome.signed_record is not None
    locator = outcome.signed_record.locator
    signature = sign(
        table="users",
        operation="update",
        fields=fields,
        locator=locator,
    )
    assert signature is not None
    assert not verify(
        table="users",
        operation="delete",
        fields=fields,
        locator=locator,
        signature=signature,
    )


@patch("app.modules.persist.user_write.write_sync")
@patch("app.modules.persist.user_write.authorize_user_write")
def test_write_user_sync_rejects_on_gate_failure(
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
    result = write_user_sync(
        operation="update",
        kind="login_touch",
        fields=build_user_fields(id=uuid4(), last_login_at=datetime.now(tz=timezone.utc)),
        reject_source="test",
    )
    assert result.ok is False
    mock_write_sync.assert_not_called()
