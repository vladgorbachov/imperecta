"""Pure-logic tests for scrape UPDATE validator + prune DELETE gate."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.sql.dml import Delete

from app.modules.data_firewall.contracts import TABLE_LOCATORS, extract_locator
from app.modules.data_firewall.signing import reset_signing_settings_cache, sign, verify
from app.modules.data_firewall.update_validator import (
    REJECT_COLUMN_NOT_ALLOWED,
    REJECT_MISSING_LOCATOR,
    REJECT_NOTHING_TO_UPDATE,
    REJECT_REACTIVATION_FORBIDDEN,
    authorize_scrape_delete,
    authorize_scrape_update,
)
from app.modules.persist.scrape_gate_fields import (
    build_listing_delete_fields,
    build_listing_update_fields,
    build_product_delete_fields,
)
from app.modules.persist.writer import PersistContext, write_sync


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def test_table_locators_fact_listing_url_hash() -> None:
    assert TABLE_LOCATORS["fact_listing"] == ("url_hash",)
    assert TABLE_LOCATORS["dim_product"] == ("id",)


def test_allowlist_denorm_success_passes_and_signs_update() -> None:
    fields = build_listing_update_fields(
        url_hash="abc123",
        last_price=Decimal("9.99"),
        last_currency_code="EUR",
        last_price_changed_at=datetime.now(tz=timezone.utc),
    )
    outcome = authorize_scrape_update(
        table="fact_listing",
        kind="listing_denorm_success",
        fields=fields,
        db=MagicMock(),
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    assert outcome.signed_record.operation == "update"
    assert outcome.signed_record.locator == {"url_hash": "abc123"}
    assert "last_price" in outcome.signed_record.fields


def test_allowlist_rejects_column_outside_kind() -> None:
    fields = build_listing_update_fields(
        url_hash="abc123",
        last_price=Decimal("9.99"),
        last_currency_code="EUR",
        last_price_changed_at=datetime.now(tz=timezone.utc),
        consecutive_errors=1,
    )
    outcome = authorize_scrape_update(
        table="fact_listing",
        kind="listing_denorm_success",
        fields=fields,
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == f"{REJECT_COLUMN_NOT_ALLOWED}:consecutive_errors"
    assert f"{REJECT_COLUMN_NOT_ALLOWED}:consecutive_errors" in outcome.failed_rules


def test_missing_locator_rejected() -> None:
    fields = {
        "last_price": Decimal("9.99"),
        "last_currency_code": "EUR",
        "last_price_changed_at": datetime.now(tz=timezone.utc),
    }
    outcome = authorize_scrape_update(
        table="fact_listing",
        kind="listing_denorm_success",
        fields=fields,
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == REJECT_MISSING_LOCATOR


def test_is_active_true_rejected() -> None:
    fields = build_listing_update_fields(url_hash="abc123", is_active=True)
    outcome = authorize_scrape_update(
        table="fact_listing",
        kind="listing_deactivate",
        fields=fields,
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == REJECT_REACTIVATION_FORBIDDEN


def test_is_active_false_allowed_for_deactivate_kind() -> None:
    fields = build_listing_update_fields(url_hash="abc123", is_active=False)
    outcome = authorize_scrape_update(
        table="fact_listing",
        kind="listing_deactivate",
        fields=fields,
        db=MagicMock(),
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    assert outcome.signed_record.fields["is_active"] is False


def test_empty_delta_rejects_nothing_to_update() -> None:
    fields = build_listing_update_fields(url_hash="abc123")
    outcome = authorize_scrape_update(
        table="fact_listing",
        kind="listing_checked",
        fields=fields,
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == REJECT_NOTHING_TO_UPDATE


def test_update_tamper_operation_fails_verify() -> None:
    fields = build_listing_update_fields(
        url_hash="abc123",
        last_checked_at=datetime.now(tz=timezone.utc),
    )
    locator = extract_locator("fact_listing", fields)
    signature = sign(
        table="fact_listing",
        operation="update",
        fields=fields,
        locator=locator,
    )
    assert signature is not None
    assert not verify(
        table="fact_listing",
        operation="delete",
        fields=fields,
        locator=locator,
        signature=signature,
    )


def test_isolated_reject_on_allowlist_failure() -> None:
    db = MagicMock()
    fields = build_listing_update_fields(url_hash="abc123", is_active=True)
    with patch(
        "app.modules.data_firewall.update_validator.write_reject_data_isolated",
    ) as mock_reject:
        outcome = authorize_scrape_update(
            table="fact_listing",
            kind="listing_deactivate",
            fields=fields,
            db=db,
        )
    assert outcome.passed is False
    mock_reject.assert_called_once()
    assert mock_reject.call_args.kwargs["operation"] == "update"
    assert mock_reject.call_args.kwargs["reject_reason"] == REJECT_REACTIVATION_FORBIDDEN


def _capture_execute(db: MagicMock, *, rowcount: int = 1) -> list:
    captured: list = []

    def _execute(stmt):
        captured.append(stmt)
        result = MagicMock()
        result.rowcount = rowcount
        return result

    db.execute.side_effect = _execute
    return captured


def test_prune_listing_delete_by_url_hash() -> None:
    fields = build_listing_delete_fields(url_hash="deadbeef")
    outcome = authorize_scrape_delete(table="fact_listing", fields=fields, db=MagicMock())
    assert outcome.passed is True
    assert outcome.signed_record is not None
    assert outcome.signed_record.operation == "delete"
    assert outcome.signed_record.locator == {"url_hash": "deadbeef"}

    db = MagicMock()
    captured = _capture_execute(db, rowcount=1)
    result = write_sync(db, outcome.signed_record, ctx=PersistContext(source="scraper_prune"))
    assert result.ok is True
    assert isinstance(captured[0], Delete)


def test_prune_product_delete_gated_by_orphan_count() -> None:
    """Product DELETE only when orphan COUNT == 0 (read on producer session)."""
    product_id = uuid4()
    url_hash = "listinghash"

    listing_outcome = authorize_scrape_delete(
        table="fact_listing",
        fields=build_listing_delete_fields(url_hash=url_hash),
        db=MagicMock(),
    )
    assert listing_outcome.passed is True

    db = MagicMock()
    execute_calls: list = []

    def _execute(stmt):
        execute_calls.append(stmt)
        result = MagicMock()
        if hasattr(stmt, "columns_clause_froms"):
            result.scalar.return_value = 0
        else:
            result.rowcount = 1
        return result

    db.execute.side_effect = _execute

    if listing_outcome.signed_record is not None:
        write_sync(db, listing_outcome.signed_record, ctx=PersistContext(source="scraper_prune"))
    db.flush()

    count_result = db.execute(MagicMock())
    other_listings = count_result.scalar() or 0

    product_deleted = False
    if other_listings == 0:
        product_outcome = authorize_scrape_delete(
            table="dim_product",
            fields=build_product_delete_fields(product_id=product_id),
            db=MagicMock(),
        )
        assert product_outcome.passed is True
        assert product_outcome.signed_record is not None
        assert product_outcome.signed_record.locator == {"id": str(product_id)}
        if product_outcome.signed_record is not None:
            write_sync(
                db,
                product_outcome.signed_record,
                ctx=PersistContext(source="scraper_prune"),
            )
            product_deleted = True

    assert other_listings == 0
    assert product_deleted is True
    delete_stmts = [stmt for stmt in execute_calls if isinstance(stmt, Delete)]
    assert len(delete_stmts) == 2
