"""Pure-logic tests for ingestion seam 2 (enrich, denorm, dim_date gate routing)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.sql.dml import Insert, Update

from app.modules.data_firewall.contracts import FACT_TABLE_CONTRACTS, TABLE_LOCATORS
from app.modules.data_firewall.firewall import FirewallOutcome, evaluate_market
from app.modules.data_firewall.signing import SignedRecord, reset_signing_settings_cache
from app.modules.data_firewall.update_validator import authorize_scrape_update
from app.modules.ingestion.service import IngestionService, _dim_date_row_for_day, _today_date_id
from app.modules.persist.scrape_gate_fields import (
    build_dim_date_fields,
    build_listing_update_fields,
    build_product_update_fields,
)
from app.modules.persist.writer import (
    PersistContext,
    PersistResult,
    SUPPORTED_WRITE_OPERATIONS,
    write_sync,
)


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def test_dim_date_registered_in_all_four_maps() -> None:
    assert "dim_date" in FACT_TABLE_CONTRACTS
    assert TABLE_LOCATORS["dim_date"] == ("date_id",)
    assert SUPPORTED_WRITE_OPERATIONS["dim_date"] == frozenset({"insert"})


def _capture_execute(db: MagicMock, *, rowcount: int = 1) -> list:
    captured: list = []

    def _execute(stmt):
        captured.append(stmt)
        result = MagicMock()
        result.rowcount = rowcount
        return result

    db.execute.side_effect = _execute
    return captured


def test_dim_date_insert_uses_on_conflict_do_nothing() -> None:
    today = date(2026, 6, 17)
    fields = _dim_date_row_for_day(today)
    outcome = evaluate_market(fields, table="dim_date", operation="insert", db=MagicMock())
    assert outcome.passed is True
    assert outcome.signed_record is not None

    db = MagicMock()
    captured = _capture_execute(db, rowcount=0)
    result = write_sync(
        db,
        outcome.signed_record,
        ctx=PersistContext(source="test", date_id=fields["date_id"]),
    )
    assert result.ok is True
    assert result.no_target is True
    assert len(captured) == 1
    stmt = captured[0]
    assert isinstance(stmt, Insert)
    assert stmt._post_values_clause is not None  # noqa: SLF001 ON CONFLICT clause present


def test_enrich_update_only_allowed_columns() -> None:
    product_id = uuid4()
    fields = build_product_update_fields(
        product_id=product_id,
        name="Real Title",
        name_normalized="real title",
    )
    outcome = authorize_scrape_update(
        table="dim_product",
        kind="product_enrich",
        fields=fields,
        db=MagicMock(),
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    assert outcome.signed_record.locator == {"id": str(product_id)}

    db = MagicMock()
    captured = _capture_execute(db)
    write_sync(db, outcome.signed_record, ctx=PersistContext(source="test"))
    assert isinstance(captured[0], Update)
    value_keys = {key.key for key in captured[0]._values.keys()}  # noqa: SLF001
    assert "id" not in value_keys
    assert value_keys == {"name", "name_normalized"}


def test_enrich_skips_when_nothing_changed() -> None:
    db = MagicMock()
    product = SimpleNamespace(
        name="Stable",
        name_normalized="stable",
        image_url="https://example.com/existing.jpg",
    )
    db.get.return_value = product
    listing = SimpleNamespace(
        id=uuid4(),
        product_id=uuid4(),
        marketplace_id=uuid4(),
        external_url="https://shop.example/item",
        url_hash="hash",
    )
    svc = IngestionService(db)
    data = SimpleNamespace(
        product_name="Stable",
        title="Stable",
        image_url="https://example.com/new.jpg",
    )
    with patch.object(svc, "_persist_scrape_update") as mock_update:
        svc._enrich_dim_product(data, listing)  # type: ignore[arg-type]
    mock_update.assert_not_called()


def test_denorm_success_routed_by_url_hash() -> None:
    fields = build_listing_update_fields(
        url_hash="listinghash",
        last_price=Decimal("12.50"),
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
    assert outcome.signed_record.locator == {"url_hash": "listinghash"}

    db = MagicMock()
    captured = _capture_execute(db)
    write_sync(db, outcome.signed_record, ctx=PersistContext(source="test"))
    assert isinstance(captured[0], Update)


def test_denorm_no_change_uses_normalized_currency_code() -> None:
    """no_change denorm writes persist_fields currency_code, not raw scrape currency."""
    normalized = "EUR"
    fields = build_listing_update_fields(
        url_hash="listinghash",
        last_checked_at=datetime.now(tz=timezone.utc),
        last_price=10.0,
        last_currency_code=normalized,
    )
    outcome = authorize_scrape_update(
        table="fact_listing",
        kind="listing_denorm_no_change",
        fields=fields,
        db=MagicMock(),
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    assert outcome.signed_record.fields["last_currency_code"] == normalized


def test_ingestion_atomicity_single_commit() -> None:
    """dim_date + enrich + fact_price + denorm share one session commit."""
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        name="product",
        name_normalized="product",
        image_url=None,
    )
    listing_id = uuid4()
    product_id = uuid4()
    marketplace_id = uuid4()
    listing = SimpleNamespace(
        id=listing_id,
        product_id=product_id,
        marketplace_id=marketplace_id,
        external_url="https://shop.example/p/1",
        url_hash="urlhash",
        last_price=None,
        last_currency_code=None,
    )
    data = SimpleNamespace(
        product_name="Widget",
        title="Widget",
        price=19.99,
        currency="EUR",
        currency_raw="EUR",
        original_price=None,
        image_url=None,
        page_role="product",
    )

    signed_price = SignedRecord(
        table="fact_price",
        operation="insert",
        locator={"listing_id": str(listing_id), "date_id": 20990101},
        fields={
            "listing_id": str(listing_id),
            "date_id": 20990101,
            "price": 19.99,
            "currency_code": "EUR",
            "scraped_at": datetime.now(tz=timezone.utc).isoformat(),
        },
        signature="sig",
    )

    with (
        patch(
            "app.modules.ingestion.service._today_date_id",
            return_value=20990101,
        ),
        patch(
            "app.modules.ingestion.service.evaluate_ecommerce",
            return_value=FirewallOutcome(
                passed=True,
                reject_reason=None,
                failed_rules=[],
                forced_log_status=None,
                page_role_verdict=None,
                signed_record=signed_price,
            ),
        ),
        patch(
            "app.modules.ingestion.service.authorize_scrape_update",
        ) as mock_auth,
        patch(
            "app.modules.ingestion.service.write_sync",
            return_value=PersistResult(ok=True, rows_affected=1),
        ) as mock_write,
    ):
        mock_auth.return_value = FirewallOutcome(
            passed=True,
            reject_reason=None,
            failed_rules=[],
            forced_log_status=None,
            page_role_verdict=None,
            signed_record=SignedRecord(
                table="fact_listing",
                operation="update",
                locator={"url_hash": "urlhash"},
                fields={"url_hash": "urlhash"},
                signature="sig2",
            ),
        )
        svc = IngestionService(db)
        svc._currency_resolver = MagicMock()
        result = svc.persist_extracted(data=data, listing=listing)  # type: ignore[arg-type]

    assert result.persisted is True
    db.commit.assert_called_once()
    assert mock_auth.call_count >= 2
    enrich_call = mock_auth.call_args_list[0].kwargs
    assert enrich_call["kind"] == "product_enrich"
    denorm_call = mock_auth.call_args_list[-1].kwargs
    assert denorm_call["kind"] == "listing_denorm_success"
    assert mock_write.call_count >= 2


def test_today_date_id_gate_insert_path(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)

    class _DT:
        @staticmethod
        def now(tz=None):
            return fixed

    monkeypatch.setattr("app.modules.ingestion.service.datetime", _DT)

    session = MagicMock()
    first = MagicMock()
    first.scalar_one_or_none.return_value = None
    third = MagicMock()
    third.scalar_one_or_none.return_value = 20260310
    session.execute.side_effect = [first, MagicMock(), third]

    with patch(
        "app.modules.ingestion.service.evaluate_market",
    ) as mock_eval, patch(
        "app.modules.ingestion.service.write_sync",
        return_value=PersistResult(ok=True, rows_affected=1),
    ):
        mock_eval.return_value = FirewallOutcome(
            passed=True,
            reject_reason=None,
            failed_rules=[],
            forced_log_status=None,
            page_role_verdict=None,
            signed_record=SignedRecord(
                table="dim_date",
                operation="insert",
                locator={"date_id": 20260310},
                fields=build_dim_date_fields(
                    date_id=20260310,
                    full_date=fixed.date(),
                    year=2026,
                    quarter=1,
                    month=3,
                    month_name="March",
                    week_iso=11,
                    day_of_month=10,
                    day_of_week=2,
                    day_name="Tuesday",
                    is_weekend=False,
                    is_last_day_of_month=False,
                ),
                signature="sig",
            ),
        )
        assert _today_date_id(session) == 20260310

    mock_eval.assert_called_once()
    assert mock_eval.call_args.kwargs["table"] == "dim_date"
    assert mock_eval.call_args.kwargs["operation"] == "insert"
