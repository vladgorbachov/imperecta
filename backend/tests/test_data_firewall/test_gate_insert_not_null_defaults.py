"""Gate INSERT field-set completeness for ORM Python defaults (no DB)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.firewall import evaluate_market
from app.modules.data_firewall.signing import reset_signing_settings_cache
from app.modules.persist.meta_write import build_scrape_job_insert_fields, write_meta_sync
from app.modules.persist.writer import build_dim_product_fields, build_fact_listing_fields


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def test_scrape_jobs_insert_fields_include_counter_defaults() -> None:
    job_id = uuid4()
    fields = build_scrape_job_insert_fields(
        id=job_id,
        job_type="discovery",
        status="pending",
        config={"domain": "shop.example"},
    )
    assert fields["total_listings"] == 0
    assert fields["successful"] == 0
    assert fields["failed"] == 0
    assert fields["skipped"] == 0

    outcome = evaluate_market(
        fields,
        table="scrape_jobs",
        operation="insert",
        db=MagicMock(),
        reject_source="test",
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    signed_fields = outcome.signed_record.fields
    assert signed_fields["total_listings"] == 0
    assert signed_fields["successful"] == 0
    assert signed_fields["failed"] == 0
    assert signed_fields["skipped"] == 0


def test_dim_product_insert_fields_include_is_active() -> None:
    product_id = uuid4()
    fields = build_dim_product_fields(
        product_id=product_id,
        name="Widget",
        name_normalized="widget",
    )
    assert fields["is_active"] is True

    outcome = evaluate_market(
        fields,
        table="dim_product",
        operation="insert",
        db=MagicMock(),
        reject_source="test",
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    assert outcome.signed_record.fields["is_active"] is True


def test_fact_listing_insert_fields_include_orm_defaults() -> None:
    product_id = uuid4()
    marketplace_id = uuid4()
    fields = build_fact_listing_fields(
        product_id=product_id,
        marketplace_id=marketplace_id,
        external_url="https://shop.example/p/1",
        url_hash="abc123",
    )
    assert fields["is_active"] is True
    assert fields["consecutive_errors"] == 0
    assert fields["scrape_interval_minutes"] == 360
    assert fields["scraper_type"] == "web_api"
    assert fields["failure_streak"] == 0

    outcome = evaluate_market(
        fields,
        table="fact_listing",
        operation="insert",
        db=MagicMock(),
        reject_source="test",
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    signed = outcome.signed_record.fields
    assert signed["consecutive_errors"] == 0
    assert signed["scrape_interval_minutes"] == 360


def test_write_meta_sync_passes_scrape_job_counters_to_gate() -> None:
    """Mock RPC boundary: counters must reach write_sync inside signed record."""
    job_id = uuid4()
    fields = build_scrape_job_insert_fields(
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
        from app.modules.persist.writer import PersistResult

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
        mock_write.return_value = PersistResult(ok=True, rows_affected=1)
        result = write_meta_sync(
            table="scrape_jobs",
            operation="insert",
            fields=fields,
            reject_source="test",
        )
    assert result.ok is True
    signed = mock_write.call_args.args[1]
    assert signed.fields["total_listings"] == 0
    assert signed.fields["successful"] == 0
    assert signed.fields["failed"] == 0
    assert signed.fields["skipped"] == 0
