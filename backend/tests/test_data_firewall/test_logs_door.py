"""Pure-logic tests for LOGS door (scrape_logs + api_logs batch signing)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.contracts import FACT_TABLE_CONTRACTS, TABLE_LOCATORS, extract_locator
from app.modules.data_firewall.firewall import evaluate_logs
from app.modules.data_firewall.signing import (
    SignedBatch,
    reset_signing_settings_cache,
    sign_batch,
    verify_batch,
)
from app.modules.persist.logs_write import build_api_log_fields, build_scrape_log_fields
from app.modules.persist.writer import PersistContext, write_batch_sync


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def _scrape_row(**overrides: object) -> dict:
    listing_id = uuid4()
    marketplace_id = uuid4()
    base = build_scrape_log_fields(
        listing_id=listing_id,
        marketplace_id=marketplace_id,
        status="success",
        url="https://shop.example/item",
        scrape_job_id=uuid4(),
        price_found=9.99,
        duration_ms=120,
        scraper_type="httpx",
    )
    base.update(overrides)
    return base


def test_logs_tables_registered_with_empty_locator() -> None:
    assert "scrape_logs" in FACT_TABLE_CONTRACTS
    assert "api_logs" in FACT_TABLE_CONTRACTS
    assert TABLE_LOCATORS["scrape_logs"] == ()
    assert TABLE_LOCATORS["api_logs"] == ()
    assert extract_locator("scrape_logs", _scrape_row()) == {}


def test_empty_locator_sign_and_verify_batch() -> None:
    rows = [_scrape_row(), _scrape_row(status="error", price_found=None)]
    locator = extract_locator("scrape_logs", rows[0])
    signature = sign_batch(table="scrape_logs", operation="insert", rows=rows, locator=locator)
    assert signature is not None
    assert verify_batch(
        table="scrape_logs",
        operation="insert",
        rows=rows,
        locator=locator,
        signature=signature,
    )


def test_evaluate_logs_well_typed_batch_inserts_on_stub() -> None:
    rows = [_scrape_row(), _scrape_row(status="price_not_found", price_found=None)]
    db = MagicMock()
    outcome = evaluate_logs(rows, table="scrape_logs", db=db, reject_source="test")
    assert outcome.inserted_count == 2
    assert outcome.rejected_count == 0
    assert outcome.signed_batch is not None
    assert len(outcome.signed_batch.rows) == 2

    session = MagicMock()
    result = write_batch_sync(
        session,
        outcome.signed_batch,
        ctx=PersistContext(source="test"),
    )
    assert result.ok is True
    assert result.rows_affected == 2
    assert session.add_all.call_count == 1


def test_tamper_on_any_row_invalidates_batch_signature() -> None:
    rows = [_scrape_row(), _scrape_row(status="error", price_found=None)]
    locator = extract_locator("scrape_logs", rows[0])
    signature = sign_batch(table="scrape_logs", operation="insert", rows=rows, locator=locator)
    tampered = [dict(rows[0]), dict(rows[1])]
    tampered[0]["price_found"] = 1.23
    assert signature is not None
    assert not verify_batch(
        table="scrape_logs",
        operation="insert",
        rows=tampered,
        locator=locator,
        signature=signature,
    )


@patch("app.modules.data_firewall.firewall.write_reject_data_isolated")
def test_mixed_batch_valid_inserted_invalid_rejected(mock_reject) -> None:
    valid = _scrape_row()
    invalid = _scrape_row(status="not_a_real_status")
    outcome = evaluate_logs(
        [valid, invalid],
        table="scrape_logs",
        db=MagicMock(),
        reject_source="test",
    )
    assert outcome.inserted_count == 1
    assert outcome.rejected_count == 1
    assert outcome.signed_batch is not None
    assert len(outcome.signed_batch.rows) == 1
    mock_reject.assert_called_once()


@patch("app.modules.scraper.service.persist_logs_batch")
def test_accumulation_flushes_one_batch(mock_persist) -> None:
    from app.modules.persist.logs_write import LogsWriteResult
    from app.modules.scraper.service import GlobalScrapeService

    mock_persist.return_value = LogsWriteResult(ok=True, inserted_count=3, rejected_count=0)

    svc = GlobalScrapeService(MagicMock(), MagicMock(), scrape_job_id=uuid4())
    listing = MagicMock()
    listing.id = uuid4()
    listing.marketplace_id = uuid4()
    listing.external_url = "https://shop.example/a"

    for status in ("success", "error", "timeout"):
        svc._persist_scrape_log(
            listing=listing,
            log_status=status,
            price_found=None,
            duration_ms=10,
            scraper_type="httpx",
            error_message=None,
            error_category=None,
            flush=False,
        )

    svc.flush_scrape_logs()
    mock_persist.assert_called_once()
    call_rows = mock_persist.call_args.kwargs["rows"]
    assert len(call_rows) == 3


def test_api_log_fields_pass_structural_contract() -> None:
    row = build_api_log_fields(
        service="market_data",
        endpoint="forex",
        method="POST",
        status="success",
    )
    outcome = evaluate_logs([row], table="api_logs", db=MagicMock(), reject_source="test")
    assert outcome.passed is True
    assert outcome.signed_batch is not None


def test_signed_batch_is_separate_from_signed_record() -> None:
    batch = SignedBatch(
        table="api_logs",
        operation="insert",
        locator={},
        rows=[build_api_log_fields(service="x", status="success")],
        signature="abc",
    )
    assert batch.table == "api_logs"
    assert hasattr(batch, "rows")
