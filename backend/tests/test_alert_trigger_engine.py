"""Alert trigger engine: pure decisions + door kinds for the firing path (no DB)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.modules.alerts import engine
from app.modules.alerts.engine import (
    decide_availability_trigger,
    decide_price_trigger,
)
from app.modules.data_firewall import alert_door

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def _price_decision(**overrides):
    kwargs = dict(
        alert_type="price_drop",
        threshold_pct=5.0,
        price=Decimal("90.00"),
        price_change_pct=Decimal("-10.0"),
        fact_price_id=42,
        product_title="Widget",
        currency="EUR",
    )
    kwargs.update(overrides)
    return decide_price_trigger(**kwargs)


class TestPriceDecision:
    def test_drop_fires_and_reconstructs_old_price(self):
        out = _price_decision()
        assert out.fire is True
        assert out.old_value == 100.00
        assert out.new_value == 90.00
        assert out.change_pct == -10.0
        assert out.fact_price_id == 42
        assert "Widget" in out.message and "dropped" in out.message

    def test_drop_below_threshold_does_not_fire(self):
        assert _price_decision(price_change_pct=Decimal("-4.9")).fire is False

    def test_rise_direction(self):
        assert _price_decision(alert_type="price_rise").fire is False
        out = _price_decision(alert_type="price_rise", price_change_pct=Decimal("6.0"))
        assert out.fire is True and "rose" in out.message

    def test_no_change_pct_never_fires(self):
        assert _price_decision(price_change_pct=None).fire is False

    def test_severity_high_at_double_threshold(self):
        assert _price_decision(price_change_pct=Decimal("-10.0")).severity == "high"
        assert _price_decision(price_change_pct=Decimal("-6.0")).severity == "medium"


class TestAvailabilityDecision:
    def test_transition_to_unavailable_is_high(self):
        out = decide_availability_trigger(
            listing_is_active=False, previous_state_active=True, product_title="W"
        )
        assert out.fire is True and out.severity == "high" and out.new_value == 0.0

    def test_transition_back_is_medium(self):
        out = decide_availability_trigger(
            listing_is_active=True, previous_state_active=False, product_title="W"
        )
        assert out.fire is True and out.severity == "medium" and out.new_value == 1.0

    def test_no_transition_no_fire(self):
        out = decide_availability_trigger(
            listing_is_active=True, previous_state_active=True, product_title="W"
        )
        assert out.fire is False


class TestCooldownAndWatermark:
    def _rule(self, **kw):
        defaults = dict(
            last_triggered_at=None,
            cooldown_minutes=60,
            created_at=NOW - timedelta(days=1),
        )
        defaults.update(kw)
        return SimpleNamespace(**defaults)

    def test_never_triggered_is_not_in_cooldown(self):
        assert engine._in_cooldown(self._rule(), NOW) is False

    def test_recent_trigger_is_in_cooldown(self):
        rule = self._rule(last_triggered_at=NOW - timedelta(minutes=30))
        assert engine._in_cooldown(rule, NOW) is True

    def test_expired_cooldown_allows_fire(self):
        rule = self._rule(last_triggered_at=NOW - timedelta(minutes=61))
        assert engine._in_cooldown(rule, NOW) is False

    def test_watermark_is_last_trigger_when_later_than_creation(self):
        rule = self._rule(last_triggered_at=NOW - timedelta(hours=1))
        assert engine._price_watermark(rule) == rule.last_triggered_at
        assert engine._price_watermark(self._rule()) == rule.created_at


class TestDoorFiringKinds:
    @pytest.fixture(autouse=True)
    def _no_reject_io(self, monkeypatch):
        monkeypatch.setattr(alert_door, "write_reject_data_isolated", lambda **kw: None)

    def _event_fields(self, **overrides):
        fields = {
            "alert_id": str(uuid4()),
            "alert_class": "analytic",
            "listing_id": str(uuid4()),
            "old_value": 100.0,
            "new_value": 90.0,
            "change_pct": -10.0,
            "message": "Widget: price dropped 10.0%",
            "severity": "high",
            "triggered_at": NOW.isoformat(),
        }
        fields.update(overrides)
        return {k: v for k, v in fields.items() if v is not None}

    def test_event_create_signs_and_targets_alert_events(self):
        with patch.object(alert_door, "_sign_fields", return_value=object()) as sign_mock:
            out = alert_door.authorize_alert_write(self._event_fields(), kind="event_create")
        assert out.passed is True
        table, operation, _ = sign_mock.call_args.args
        assert table == "alert_events" and operation == "insert"

    def test_event_create_requires_message(self):
        out = alert_door.authorize_alert_write(
            self._event_fields(message="  "), kind="event_create"
        )
        assert out.passed is False
        assert "message_required" in out.failed_rules

    def test_event_create_rejects_bad_severity(self):
        out = alert_door.authorize_alert_write(
            self._event_fields(severity="apocalyptic"), kind="event_create"
        )
        assert out.passed is False
        assert "severity_invalid" in out.failed_rules

    def test_event_create_rejects_foreign_fields(self):
        out = alert_door.authorize_alert_write(
            self._event_fields(ai_confidence=0.9), kind="event_create"
        )
        assert out.passed is False
        assert any(rule.startswith("field:ai_confidence") for rule in out.failed_rules)

    def test_rule_trigger_signs_bookkeeping_update(self):
        with patch.object(alert_door, "_sign_fields", return_value=object()) as sign_mock:
            out = alert_door.authorize_alert_write(
                {
                    "id": str(uuid4()),
                    "last_triggered_at": NOW.isoformat(),
                    "trigger_count": 3,
                },
                kind="rule_trigger",
            )
        assert out.passed is True
        table, operation, _ = sign_mock.call_args.args
        assert table == "alerts" and operation == "update"

    def test_rule_trigger_requires_timestamp_and_positive_count(self):
        out = alert_door.authorize_alert_write(
            {"id": str(uuid4()), "trigger_count": 0}, kind="rule_trigger"
        )
        assert out.passed is False
        assert "last_triggered_at_required" in out.failed_rules
        assert "trigger_count_invalid" in out.failed_rules

    def test_rule_trigger_cannot_flip_activity(self):
        out = alert_door.authorize_alert_write(
            {
                "id": str(uuid4()),
                "last_triggered_at": NOW.isoformat(),
                "trigger_count": 1,
                "is_active": False,
            },
            kind="rule_trigger",
        )
        assert out.passed is False
        assert any(rule.startswith("field:is_active") for rule in out.failed_rules)
