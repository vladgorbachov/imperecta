"""Gate registration for service_alerts (artefact 3 write path, no writer wired)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.contracts import FACT_TABLE_CONTRACTS, TABLE_LOCATORS
from app.modules.data_firewall.firewall import evaluate_market
from app.modules.data_firewall.signing import reset_signing_settings_cache
from app.modules.persist.service_alerts_write import build_service_alert_fields


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def test_service_alerts_contract_and_locator_registered() -> None:
    assert "service_alerts" in FACT_TABLE_CONTRACTS
    assert TABLE_LOCATORS["service_alerts"] == ("id",)
    contract = FACT_TABLE_CONTRACTS["service_alerts"]
    assert contract["alert_class"]["nullable"] is False
    assert contract["module"]["nullable"] is False


def test_build_service_alert_fields_signs_through_gate() -> None:
    row_id = uuid4()
    fields = build_service_alert_fields(
        id=row_id,
        module="discovery",
        submodule="budget_governor",
        severity="warning",
        anomaly_type="detector_divergence",
        message="test anomaly",
        context={"detail": "ok"},
    )
    assert fields["alert_class"] == "service"
    outcome = evaluate_market(
        fields,
        table="service_alerts",
        operation="insert",
        db=MagicMock(),
        reject_source="test",
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    assert outcome.signed_record.locator == {"id": str(row_id)}
