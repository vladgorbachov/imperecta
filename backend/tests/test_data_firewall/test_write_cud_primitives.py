"""Pure-logic tests for persist UPDATE/DELETE primitives (no DB/network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.sql.dml import Delete, Update

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


def _capture_execute(db: MagicMock, *, rowcount: int = 1) -> list:
    captured: list = []

    def _execute(stmt):
        captured.append(stmt)
        result = MagicMock()
        result.rowcount = rowcount
        return result

    db.execute.side_effect = _execute
    return captured


def test_supported_write_operations_matrix() -> None:
    assert SUPPORTED_WRITE_OPERATIONS["scrape_jobs"] == frozenset({"insert", "update", "delete"})
    assert SUPPORTED_WRITE_OPERATIONS["dim_marketplace"] == frozenset({"insert", "update", "delete"})
    assert SUPPORTED_WRITE_OPERATIONS["fact_listing"] == frozenset({"insert", "update", "delete"})
    assert SUPPORTED_WRITE_OPERATIONS["fact_price"] == frozenset({"insert", "delete"})
    assert SUPPORTED_WRITE_OPERATIONS["fact_currency_rate"] == frozenset({"insert", "delete"})
    assert "update" not in SUPPORTED_WRITE_OPERATIONS["fact_price"]


def test_update_locates_by_locator_sets_non_locator_fields() -> None:
    product_id = uuid4()
    fields = build_dim_product_fields(
        product_id=product_id,
        name="Renamed",
        name_normalized="renamed",
        is_active=False,
    )
    signed = _signed("dim_product", "update", fields)
    db = MagicMock()
    captured = _capture_execute(db, rowcount=1)

    result = write_sync(db, signed, ctx=PersistContext(source="test"))

    assert result.ok is True
    assert result.rows_affected == 1
    assert result.no_target is False
    assert len(captured) == 1
    stmt = captured[0]
    assert isinstance(stmt, Update)
    # SET must not include locator column id
    value_keys = {key.key for key in stmt._values.keys()}  # noqa: SLF001
    assert "id" not in value_keys
    assert "name" in value_keys
    assert "is_active" in value_keys
    db.add.assert_not_called()


def test_update_empty_value_fields_rejects() -> None:
    product_id = uuid4()
    fields = {"id": product_id}
    signed = _signed("dim_product", "update", fields)
    db = MagicMock()

    result = write_sync(db, signed, ctx=PersistContext(source="test"))

    assert result.ok is False
    db.execute.assert_not_called()


def test_update_zero_rows_honest_no_target_notice() -> None:
    product_id = uuid4()
    fields = build_dim_product_fields(
        product_id=product_id,
        name="Renamed",
        name_normalized="renamed",
    )
    signed = _signed("dim_product", "update", fields)
    db = MagicMock()
    _capture_execute(db, rowcount=0)

    result = write_sync(db, signed, ctx=PersistContext(source="test"))

    assert result.ok is True
    assert result.rows_affected == 0
    assert result.no_target is True


def test_delete_by_locator_returns_rows_affected() -> None:
    fields = {"url_hash": "abc123hash"}
    signed = _signed("fact_listing", "delete", fields)
    db = MagicMock()
    captured = _capture_execute(db, rowcount=2)

    result = write_sync(db, signed, ctx=PersistContext(source="test"))

    assert result.ok is True
    assert result.rows_affected == 2
    assert isinstance(captured[0], Delete)
    db.add.assert_not_called()


def test_delete_zero_rows_honest_no_target_notice() -> None:
    fields = {
        "date_id": 20250617,
        "currency_code": "EUR",
        "source": "ecb",
    }
    signed = _signed("fact_currency_rate", "delete", fields)
    db = MagicMock()
    _capture_execute(db, rowcount=0)

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


def test_insert_callers_still_truthy_on_success() -> None:
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
    db.add.assert_called_once()


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
