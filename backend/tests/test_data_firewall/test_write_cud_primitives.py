"""Pure-logic tests for persist UPDATE/DELETE primitives (no DB/network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.sql.dml import Delete

from app.modules.data_firewall.contracts import extract_locator
from app.modules.data_firewall.signing import SignedRecord, reset_signing_settings_cache, sign
from app.modules.persist.writer import (
    PersistContext,
    SUPPORTED_WRITE_OPERATIONS,
    build_dim_product_fields,
    write_async,
    write_sync,
)


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def _signed(
    table: str,
    operation: str,
    fields: dict,
) -> SignedRecord:
    locator = extract_locator(table, fields)
    signature = sign(table=table, operation=operation, fields=fields, locator=locator)
    assert signature is not None
    return SignedRecord(
        table=table,
        operation=operation,
        locator=locator,
        fields=fields,
        signature=signature,
    )


@patch("app.modules.persist.writer.exec_write_record")
def test_update_locates_by_locator_sets_non_locator_fields(mock_exec: MagicMock) -> None:
    mock_exec.return_value = 1
    product_id = uuid4()
    fields = build_dim_product_fields(
        product_id=product_id,
        name="Renamed",
        name_normalized="renamed",
        is_active=False,
    )
    signed = _signed("dim_product", "update", fields)
    db = MagicMock()

    result = write_sync(db, signed, ctx=PersistContext(source="test"))

    assert result.ok is True
    assert result.rows_affected == 1
    assert result.no_target is False
    mock_exec.assert_called_once_with(db, signed)
    db.add.assert_not_called()


def test_update_empty_value_fields_rejects() -> None:
    product_id = uuid4()
    fields = {"id": product_id}
    signed = _signed("dim_product", "update", fields)
    db = MagicMock()

    result = write_sync(db, signed, ctx=PersistContext(source="test"))

    assert result.ok is False
    db.execute.assert_not_called()


@patch("app.modules.persist.writer.exec_write_record")
def test_update_zero_rows_honest_no_target_notice(mock_exec: MagicMock) -> None:
    mock_exec.return_value = 0
    product_id = uuid4()
    fields = build_dim_product_fields(
        product_id=product_id,
        name="Renamed",
        name_normalized="renamed",
    )
    signed = _signed("dim_product", "update", fields)
    db = MagicMock()

    result = write_sync(db, signed, ctx=PersistContext(source="test"))

    assert result.ok is True
    assert result.rows_affected == 0
    assert result.no_target is True


@patch("app.modules.persist.writer.exec_write_record")
def test_delete_by_locator_returns_rows_affected(mock_exec: MagicMock) -> None:
    mock_exec.return_value = 2
    fields = {"url_hash": "abc123hash"}
    signed = _signed("fact_listing", "delete", fields)
    db = MagicMock()

    result = write_sync(db, signed, ctx=PersistContext(source="test"))

    assert result.ok is True
    assert result.rows_affected == 2
    mock_exec.assert_called_once_with(db, signed)
    db.add.assert_not_called()


@patch("app.modules.persist.writer.exec_write_record")
def test_delete_zero_rows_honest_no_target_notice(mock_exec: MagicMock) -> None:
    mock_exec.return_value = 0
    fields = {
        "date_id": 20250617,
        "currency_code": "EUR",
        "source": "ecb",
    }
    signed = _signed("fact_currency_rate", "delete", fields)
    db = MagicMock()

    result = write_sync(db, signed, ctx=PersistContext(source="test"))

    assert result.ok is True
    assert result.rows_affected == 0
    assert result.no_target is True


def test_update_tampered_signature_rejected() -> None:
    product_id = uuid4()
    fields = build_dim_product_fields(
        product_id=product_id,
        name="Renamed",
        name_normalized="renamed",
    )
    signed = _signed("dim_product", "update", fields)
    tampered = SignedRecord(
        table=signed.table,
        operation="delete",
        locator=signed.locator,
        fields=signed.fields,
        signature=signed.signature,
    )
    db = MagicMock()

    result = write_sync(db, tampered, ctx=PersistContext(source="test"))

    assert result.ok is False
    db.execute.assert_not_called()


def test_update_unsupported_on_replace_table_rejected() -> None:
    listing_id = uuid4()
    from datetime import datetime, timezone

    from app.modules.persist.writer import build_fact_price_fields

    fields = build_fact_price_fields(
        listing_id=listing_id,
        date_id=20990101,
        price=1.0,
        currency_code="EUR",
        original_price=None,
        discount_pct=None,
        price_change_pct=None,
        scraped_at=datetime.now(tz=timezone.utc),
        scrape_job_id=None,
    )
    signed = _signed("fact_price", "update", fields)
    db = MagicMock()

    result = write_sync(db, signed, ctx=PersistContext(source="test"))

    assert result.ok is False
    db.execute.assert_not_called()


@patch("app.modules.persist.writer.exec_write_record")
def test_insert_callers_still_truthy_on_success(mock_exec: MagicMock) -> None:
    mock_exec.return_value = 1
    product_id = uuid4()
    fields = build_dim_product_fields(
        product_id=product_id,
        name="Item",
        name_normalized="item",
    )
    signed = _signed("dim_product", "insert", fields)
    db = MagicMock()

    result = write_sync(db, signed, ctx=PersistContext(source="test"))

    assert result
    assert result.ok is True
    mock_exec.assert_called_once()
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_write_async_delete_mirror() -> None:
    fields = {
        "date_id": 20250617,
        "symbol": "BTC",
        "source": "coingecko",
    }
    signed = _signed("fact_crypto_price", "delete", fields)
    db = MagicMock()
    db.sync_session = MagicMock()
    execute_result = MagicMock()
    execute_result.rowcount = 1
    db.execute = AsyncMock(return_value=execute_result)

    result = await write_async(db, signed, ctx=PersistContext(source="market_crypto"))

    assert result.ok is True
    assert result.rows_affected == 1
    stmt = db.execute.await_args.args[0]
    assert isinstance(stmt, Delete)
