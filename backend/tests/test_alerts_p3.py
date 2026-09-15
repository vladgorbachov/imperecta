"""P3 alert door semantics + persist payload completeness (no DB)."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.modules.data_firewall import alert_door
from app.modules.persist.alerts_write import build_alert_rule_fields


@pytest.fixture(autouse=True)
def _no_reject_io(monkeypatch):
    monkeypatch.setattr(alert_door, "write_reject_data_isolated", lambda **kw: None)


def _create_fields(**overrides):
    fields = build_alert_rule_fields(
        id=uuid4(),
        user_id=uuid4(),
        alert_type="price_drop",
        threshold_pct=5.0,
        channel="email",
        cooldown_minutes=60,
        is_active=True,
        trigger_count=0,
        alert_class="analytic",
    )
    fields.update(overrides)
    return {k: v for k, v in fields.items() if v is not None}


def test_rule_create_signs_valid_payload():
    with patch.object(alert_door, "_sign_fields", return_value=object()) as sign_mock:
        out = alert_door.authorize_alert_write(_create_fields(), kind="rule_create")
    assert out.passed is True
    sign_mock.assert_called_once()


def test_rule_create_requires_user_id():
    fields = _create_fields()
    fields.pop("user_id")
    out = alert_door.authorize_alert_write(fields, kind="rule_create")
    assert out.passed is False
    assert "user_id_required" in out.failed_rules


def test_unknown_alert_type_rejected():
    out = alert_door.authorize_alert_write(
        _create_fields(alert_type="moon_phase"), kind="rule_create"
    )
    assert out.passed is False
    assert "alert_type_invalid" in out.failed_rules


def test_webhook_channel_requires_https_url():
    out = alert_door.authorize_alert_write(
        _create_fields(channel="webhook"), kind="rule_create"
    )
    assert out.passed is False
    assert "webhook_url_https_required" in out.failed_rules

    with patch.object(alert_door, "_sign_fields", return_value=object()):
        ok = alert_door.authorize_alert_write(
            _create_fields(channel="webhook", webhook_url="https://hooks.example/x"),
            kind="rule_create",
        )
    assert ok.passed is True


def test_field_outside_allowlist_rejected():
    out = alert_door.authorize_alert_write(
        _create_fields(trigger_count=999, last_triggered_at="2026-01-01"),
        kind="rule_create",
    )
    assert out.passed is False
    assert any(rule.startswith("field:last_triggered_at") for rule in out.failed_rules)


def test_rule_update_cannot_touch_ownership():
    out = alert_door.authorize_alert_write(
        {"id": str(uuid4()), "user_id": str(uuid4()), "is_active": False},
        kind="rule_update",
    )
    assert out.passed is False
    assert any(rule.startswith("field:user_id") for rule in out.failed_rules)


def test_threshold_bounds():
    out = alert_door.authorize_alert_write(
        _create_fields(threshold_pct=250), kind="rule_create"
    )
    assert out.passed is False
    assert "threshold_pct_out_of_range" in out.failed_rules


def test_rule_delete_locator_only():
    with patch.object(alert_door, "_sign_fields", return_value=object()):
        out = alert_door.authorize_alert_write(
            {"id": str(uuid4())}, kind="rule_delete"
        )
    assert out.passed is True
