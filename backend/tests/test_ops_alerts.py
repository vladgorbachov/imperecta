"""ops_alerts emitter: rate limiting, validation, fail-open (no DB)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.common import ops_alerts


@pytest.fixture(autouse=True)
def _fresh_limiter():
    ops_alerts._last_emit.clear()
    yield
    ops_alerts._last_emit.clear()


def _emit(**overrides):
    kwargs = dict(
        module="scraper",
        submodule="listing",
        severity="warning",
        anomaly_type="listing_failure_streak",
        message="test",
        entity="mp-1",
    )
    kwargs.update(overrides)
    return ops_alerts.emit_ops_alert(**kwargs)


def test_emits_through_gate_writer():
    with patch.object(
        ops_alerts, "write_service_alert_sync", return_value=MagicMock(ok=True)
    ) as writer:
        assert _emit() is True
    fields = writer.call_args.kwargs["fields"]
    assert fields["module"] == "scraper"
    assert fields["anomaly_type"] == "listing_failure_streak"
    assert writer.call_args.kwargs["reject_source"] == "scraper"


def test_rate_limits_same_entity_but_not_other_entities():
    with patch.object(
        ops_alerts, "write_service_alert_sync", return_value=MagicMock(ok=True)
    ) as writer:
        assert _emit() is True
        assert _emit() is False  # same key suppressed
        assert _emit(entity="mp-2") is True  # different entity passes
        assert _emit(anomaly_type="listing_deactivated") is True  # different anomaly
    assert writer.call_count == 3


def test_invalid_severity_refused():
    with patch.object(ops_alerts, "write_service_alert_sync") as writer:
        assert _emit(severity="apocalyptic") is False
    writer.assert_not_called()


def test_fail_open_on_writer_crash():
    with patch.object(
        ops_alerts, "write_service_alert_sync", side_effect=RuntimeError("db down")
    ):
        assert _emit() is False  # swallowed, no raise


class TestQualityGateAlerts:
    def _report(self, **overrides):
        report = {"score": 30, "grade": "F", "flags": ["missing_title"], "critical": True}
        report.update(overrides)
        return report

    def test_critical_report_emits_quality_alert(self):
        from app.modules.data_firewall import quality_gate

        with patch.object(quality_gate, "emit_ops_alert") as emit:
            quality_gate._alert_on_report(
                self._report(), url="https://x.example/p", marketplace_id="mp-9"
            )
        assert emit.call_args.kwargs["module"] == "quality"
        assert emit.call_args.kwargs["anomaly_type"] == "quality_critical"
        assert emit.call_args.kwargs["entity"] == "mp-9"

    def test_low_score_noncritical_emits_info(self):
        from app.modules.data_firewall import quality_gate

        with patch.object(quality_gate, "emit_ops_alert") as emit:
            quality_gate._alert_on_report(
                self._report(critical=False, flags=["missing_image"], score=35),
                url=None,
                marketplace_id=None,
            )
        assert emit.call_args.kwargs["anomaly_type"] == "quality_low_score"
        assert emit.call_args.kwargs["severity"] == "info"

    def test_healthy_report_is_silent(self):
        from app.modules.data_firewall import quality_gate

        with patch.object(quality_gate, "emit_ops_alert") as emit:
            quality_gate._alert_on_report(
                self._report(critical=False, score=95, grade="A", flags=[]),
                url=None,
                marketplace_id="mp",
            )
        emit.assert_not_called()
