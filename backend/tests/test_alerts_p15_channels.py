"""P15: in_app channel + multi-channel `channels` set (door, service, engine — no DB)."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.modules.alerts.schemas import AlertRule, AlertRuleCreate
from app.modules.alerts.service import normalize_channels, rule_channels
from app.modules.data_firewall import alert_door
from app.modules.persist.alerts_write import build_alert_rule_fields


@pytest.fixture(autouse=True)
def _no_reject_io(monkeypatch):
    monkeypatch.setattr(alert_door, "write_reject_data_isolated", lambda **kw: None)


def _create_fields(**overrides):
    fields = build_alert_rule_fields(
        id=uuid4(),
        user_id=uuid4(),
        alert_type="price_rise",
        threshold_pct=4.0,
        channel="in_app",
        channels=["in_app"],
        cooldown_minutes=60,
        is_active=True,
        trigger_count=0,
        alert_class="analytic",
    )
    fields.update(overrides)
    return {k: v for k, v in fields.items() if v is not None}


class _FakeRule:
    def __init__(self, channel=None, channels=None, webhook_url=None):
        self.channel = channel
        self.channels = channels
        self.webhook_url = webhook_url


# --- API schema -------------------------------------------------------------


def test_schema_accepts_the_deployed_frontend_payload():
    """The exact payload from docs/BACKEND_REQUESTS_2026-09-18.md §1 (was 422)."""
    body = AlertRuleCreate(
        listing_id=uuid4(),
        alert_type="price_rise",
        threshold_pct=4,
        channel="in_app",
        channels=["in_app"],
        webhook_url=None,
        cooldown_minutes=60,
    )
    assert body.channel == "in_app"
    assert body.channels == ["in_app"]


def test_rule_response_carries_channels():
    assert "channels" in AlertRule.model_fields


# --- Door semantics ---------------------------------------------------------


def test_door_accepts_in_app_channel_and_channels_set():
    with patch.object(alert_door, "_sign_fields", return_value=object()):
        out = alert_door.authorize_alert_write(_create_fields(), kind="rule_create")
    assert out.passed is True


def test_door_accepts_multi_channel_set():
    fields = _create_fields(channel="email", channels=["email", "telegram", "in_app"])
    with patch.object(alert_door, "_sign_fields", return_value=object()):
        out = alert_door.authorize_alert_write(fields, kind="rule_create")
    assert out.passed is True


def test_door_rejects_unknown_channel_in_set():
    out = alert_door.authorize_alert_write(
        _create_fields(channels=["in_app", "pigeon"]), kind="rule_create"
    )
    assert out.passed is False
    assert "channels_value_invalid" in out.failed_rules


def test_door_rejects_empty_and_duplicate_sets():
    out = alert_door.authorize_alert_write(
        _create_fields(channels=[]), kind="rule_create"
    )
    # Empty list is stripped by the None-filter upstream, so force it through.
    fields = _create_fields()
    fields["channels"] = []
    out = alert_door.authorize_alert_write(fields, kind="rule_create")
    assert out.passed is False
    assert "channels_invalid" in out.failed_rules

    out = alert_door.authorize_alert_write(
        _create_fields(channels=["in_app", "in_app"]), kind="rule_create"
    )
    assert out.passed is False
    assert "channels_duplicate" in out.failed_rules


def test_webhook_in_channels_requires_https_url():
    out = alert_door.authorize_alert_write(
        _create_fields(channel="in_app", channels=["in_app", "webhook"]),
        kind="rule_create",
    )
    assert out.passed is False
    assert "webhook_url_https_required" in out.failed_rules

    fields = _create_fields(
        channel="in_app",
        channels=["in_app", "webhook"],
        webhook_url="https://ops.example/hook",
    )
    with patch.object(alert_door, "_sign_fields", return_value=object()):
        out = alert_door.authorize_alert_write(fields, kind="rule_create")
    assert out.passed is True


def test_webhook_url_without_webhook_in_set_rejected():
    out = alert_door.authorize_alert_write(
        _create_fields(webhook_url="https://ops.example/hook"),
        kind="rule_create",
    )
    assert out.passed is False
    assert "webhook_url_only_for_webhook_channel" in out.failed_rules


def test_event_sent_via_accepts_in_app():
    fields = {
        "alert_id": str(uuid4()),
        "alert_class": "analytic",
        "message": "x",
        "severity": "medium",
        "sent_via": "in_app",
        "triggered_at": "2026-09-18T00:00:00+00:00",
    }
    with patch.object(alert_door, "_sign_fields", return_value=object()):
        out = alert_door.authorize_alert_write(fields, kind="event_create")
    assert out.passed is True


# --- Service helpers --------------------------------------------------------


def test_normalize_channels_defaults_and_dedupes():
    assert normalize_channels({"channel": "in_app"}) == ["in_app"]
    assert normalize_channels({}) == ["email"]
    assert normalize_channels(
        {"channel": "email", "channels": ["email", "in_app", "email"]}
    ) == ["email", "in_app"]


def test_rule_channels_falls_back_to_legacy_column():
    assert rule_channels(_FakeRule(channel="telegram", channels=None)) == ["telegram"]
    assert rule_channels(_FakeRule(channel="email", channels=[])) == ["email"]
    assert rule_channels(
        _FakeRule(channel="email", channels=["in_app", "email"])
    ) == ["in_app", "email"]


# --- Engine fan-out ---------------------------------------------------------


def test_engine_in_app_counts_as_delivered_without_external_send():
    import asyncio

    from app.modules.alerts.engine import TriggerDecision, _deliver

    rule = _FakeRule(channel="in_app", channels=["in_app"])
    rule.id = uuid4()
    rule.listing_id = None
    rule.alert_type = "price_rise"
    decision = TriggerDecision(fire=True, message="x")

    class _User:
        email = None
        telegram_chat_id = None

    delivered = asyncio.run(_deliver(rule, _User(), decision))
    assert delivered == ["in_app"]


def test_engine_fans_out_and_skips_failed_external(monkeypatch):
    import asyncio

    from app.modules.alerts import engine as engine_mod

    class _OkChannel:
        async def send(self, recipient, message):
            return True

    class _DeadChannel:
        async def send(self, recipient, message):
            raise RuntimeError("smtp down")

    monkeypatch.setitem(engine_mod._CHANNELS, "email", _DeadChannel())
    monkeypatch.setitem(engine_mod._CHANNELS, "telegram", _OkChannel())

    rule = _FakeRule(channel="email", channels=["email", "telegram", "in_app"])
    rule.id = uuid4()
    rule.listing_id = None
    rule.alert_type = "price_rise"

    class _User:
        email = "u@example.test"
        telegram_chat_id = 42

    delivered = asyncio.run(
        engine_mod._deliver(rule, _User(), engine_mod.TriggerDecision(fire=True, message="x"))
    )
    assert delivered == ["telegram", "in_app"]
