"""Pure-logic tests for META door (scrape_jobs + dim_marketplace)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.contracts import FACT_TABLE_CONTRACTS, TABLE_LOCATORS, extract_locator
from app.modules.data_firewall.firewall import evaluate_market
from app.modules.data_firewall.signing import reset_signing_settings_cache, sign, verify
from app.modules.persist.meta_write import (
    build_dim_marketplace_fields,
    build_scrape_job_fields,
    write_meta_sync,
)


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def test_meta_tables_registered_in_maps() -> None:
    assert "scrape_jobs" in FACT_TABLE_CONTRACTS
    assert "dim_marketplace" in FACT_TABLE_CONTRACTS
    assert TABLE_LOCATORS["scrape_jobs"] == ("id",)
    assert TABLE_LOCATORS["dim_marketplace"] == ("id",)


def test_evaluate_market_signs_scrape_jobs_insert() -> None:
    job_id = uuid4()
    fields = build_scrape_job_fields(
        id=job_id,
        job_type="discovery",
        status="pending",
        config={"domain": "shop.example"},
    )
    outcome = evaluate_market(
        fields,
        table="scrape_jobs",
        operation="insert",
        db=MagicMock(),
        reject_source="test",
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    assert outcome.signed_record.operation == "insert"
    assert outcome.signed_record.locator == {"id": str(job_id)}


def test_evaluate_market_tamper_operation_fails_verify() -> None:
    job_id = uuid4()
    fields = build_scrape_job_fields(id=job_id, status="running")
    locator = extract_locator("scrape_jobs", fields)
    signature = sign(
        table="scrape_jobs",
        operation="update",
        fields=fields,
        locator=locator,
    )
    assert signature is not None
    assert not verify(
        table="scrape_jobs",
        operation="delete",
        fields=fields,
        locator=locator,
        signature=signature,
    )


def test_build_scrape_job_fields_include_id_for_update() -> None:
    job_id = uuid4()
    fields = build_scrape_job_fields(id=job_id, status="running")
    assert fields["id"] == str(job_id)
    assert "status" in fields


def test_build_dim_marketplace_insert_has_required_columns() -> None:
    mp_id = uuid4()
    fields = build_dim_marketplace_fields(
        id=mp_id,
        marketplace_code="shop_example",
        name="Shop",
        source_type="marketplace",
        country_code="DE",
        operates_in=["DE"],
        domain="shop.example",
        base_url="https://shop.example",
        api_available=False,
        currency_code="EUR",
        scraper_type="web_api",
        is_active=True,
    )
    assert fields["id"] == str(mp_id)
    assert fields["marketplace_code"] == "shop_example"


def test_jsonb_config_passes_structural_contract() -> None:
    job_id = uuid4()
    fields = build_scrape_job_fields(
        id=job_id,
        job_type="discovery",
        status="running",
        config={"metadata": {"worker_log_tail": ["line"], "nested": {"ok": True}}},
    )
    outcome = evaluate_market(fields, table="scrape_jobs", operation="update", db=MagicMock())
    assert outcome.passed is True


def test_write_meta_sync_dispatches_insert_with_commit() -> None:
    job_id = uuid4()
    fields = build_scrape_job_fields(
        id=job_id,
        job_type="discovery",
        status="pending",
        config={},
    )
    db = MagicMock()
    with patch("app.modules.persist.meta_write.sync_session_factory", return_value=db), patch(
        "app.modules.persist.meta_write.evaluate_market",
    ) as mock_eval, patch("app.modules.persist.meta_write.write_sync") as mock_write:
        from app.modules.data_firewall.firewall import FirewallOutcome
        from app.modules.data_firewall.signing import SignedRecord

        mock_eval.return_value = FirewallOutcome(
            passed=True,
            reject_reason=None,
            failed_rules=[],
            forced_log_status=None,
            page_role_verdict=None,
            signed_record=SignedRecord(
                table="scrape_jobs",
                operation="insert",
                locator={"id": str(job_id)},
                fields=fields,
                signature="sig",
            ),
        )
        from app.modules.persist.writer import PersistResult

        mock_write.return_value = PersistResult(ok=True, rows_affected=1)
        result = write_meta_sync(
            table="scrape_jobs",
            operation="insert",
            fields=fields,
            reject_source="test",
        )
    assert result.ok is True
    db.commit.assert_called_once()
    db.close.assert_called_once()
    mock_write.assert_called_once()
    assert mock_write.call_args.args[1].operation == "insert"


def test_scrape_jobs_finalize_update_accepts_failed_counter() -> None:
    """Regression: integer failed must not inherit status enum check_values."""
    job_id = uuid4()
    completed_at = datetime.now(timezone.utc)
    for failed_count in (0, 1):
        fields = build_scrape_job_fields(
            id=job_id,
            status="completed",
            completed_at=completed_at,
            duration_ms=1200,
            total_listings=10,
            successful=8,
            failed=failed_count,
            config={"domain": "shop.example"},
        )
        outcome = evaluate_market(
            fields,
            table="scrape_jobs",
            operation="update",
            db=MagicMock(),
            reject_source="test",
        )
        assert outcome.passed is True, f"failed={failed_count} should pass gate"


def test_scrape_jobs_finalize_update_rejects_invalid_status() -> None:
    job_id = uuid4()
    fields = build_scrape_job_fields(
        id=job_id,
        status="not_a_valid_status",
        completed_at=datetime.now(timezone.utc),
        duration_ms=100,
        total_listings=0,
        successful=0,
        failed=0,
        config={},
    )
    outcome = evaluate_market(
        fields,
        table="scrape_jobs",
        operation="update",
        db=MagicMock(),
        reject_source="test",
    )
    assert outcome.passed is False
    assert "check:status" in outcome.failed_rules
