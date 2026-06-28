"""B2 length-prefixed signing canonical — byte-exact and tamper tests (no DB)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.data_firewall.signing import (
    canonical_serialize_signed_batch_payload,
    canonical_serialize_signed_payload,
    reset_signing_settings_cache,
    sign,
    sign_batch,
    verify,
    verify_batch,
)

_SECRET = "unit-test-data-firewall-secret"

_EXPECTED_RECORD_BYTES = (
    b"T5:usersO6:updateLD0FD126:amountS5:12.345:asciiS5:plain5:countS2:428:cyrillicS12:"
    b"\xd0\x9f\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x823:dayS10:2026-06-274:flagS4:true"
    b"7:missingN5:prefsS13:{\"a\":1,\"b\":2}5:ratioS3:0.14:tagsS9:[\"z\",\"a\"]"
    b"3:uidS36:00000000-0000-0000-0000-0000000000014:whenS25:2026-06-27T12:00:00+00:00"
)

_EXPECTED_BATCH_BYTES = (
    b"T11:scrape_logsO6:insertLD0R2D210:listing_idS36:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    b"6:statusS7:successD210:listing_idS36:bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb6:statusS5:error"
)


@pytest.fixture(autouse=True)
def _signing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", _SECRET)
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def _all_type_fields() -> dict:
    return {
        "amount": Decimal("12.34"),
        "ascii": "plain",
        "count": 42,
        "cyrillic": "Привет",
        "day": date(2026, 6, 27),
        "flag": True,
        "missing": None,
        "prefs": {"b": 2, "a": 1},
        "ratio": 0.1,
        "tags": ["z", "a"],
        "uid": UUID("00000000-0000-0000-0000-000000000001"),
        "when": datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc),
    }


def test_record_canonical_bytes_exact_all_value_types() -> None:
    fields = _all_type_fields()
    canonical = canonical_serialize_signed_payload(
        table="users",
        operation="update",
        fields=fields,
        locator={},
    )
    assert canonical == _EXPECTED_RECORD_BYTES


def test_record_sign_verify_and_tamper_rejects() -> None:
    fields = _all_type_fields()
    locator: dict = {}
    signature = sign(
        table="users",
        operation="update",
        fields=fields,
        locator=locator,
    )
    assert signature is not None
    assert verify(
        table="users",
        operation="update",
        fields=fields,
        locator=locator,
        signature=signature,
    )

    assert not verify(
        table="dim_product",
        operation="update",
        fields=fields,
        locator=locator,
        signature=signature,
    )
    assert not verify(
        table="users",
        operation="insert",
        fields=fields,
        locator=locator,
        signature=signature,
    )

    tampered_fields = dict(fields)
    tampered_fields["count"] = 99
    assert not verify(
        table="users",
        operation="update",
        fields=tampered_fields,
        locator=locator,
        signature=signature,
    )

    tampered_fields = dict(fields)
    tampered_fields["prefs"] = {"a": 1, "b": 3}
    assert not verify(
        table="users",
        operation="update",
        fields=tampered_fields,
        locator=locator,
        signature=signature,
    )

    tampered_fields = dict(fields)
    tampered_fields["cyrillic"] = "Другой"
    assert not verify(
        table="users",
        operation="update",
        fields=tampered_fields,
        locator=locator,
        signature=signature,
    )

    locator_with_key = {"id": "00000000-0000-0000-0000-000000000099"}
    signed_locator = sign(
        table="users",
        operation="update",
        fields=fields,
        locator=locator_with_key,
    )
    assert signed_locator is not None
    tampered_locator = dict(locator_with_key)
    tampered_locator["id"] = "00000000-0000-0000-0000-000000000001"
    assert not verify(
        table="users",
        operation="update",
        fields=fields,
        locator=tampered_locator,
        signature=signed_locator,
    )


def test_batch_canonical_bytes_exact_and_row_order_sensitive() -> None:
    row_a = {
        "listing_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "status": "success",
    }
    row_b = {
        "listing_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "status": "error",
    }
    canonical = canonical_serialize_signed_batch_payload(
        table="scrape_logs",
        operation="insert",
        rows=[row_a, row_b],
        locator={},
    )
    assert canonical == _EXPECTED_BATCH_BYTES

    reversed_canonical = canonical_serialize_signed_batch_payload(
        table="scrape_logs",
        operation="insert",
        rows=[row_b, row_a],
        locator={},
    )
    assert reversed_canonical != canonical


def test_batch_sign_verify_and_row_tamper_rejects() -> None:
    row_a = {
        "listing_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "status": "success",
    }
    row_b = {
        "listing_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "status": "error",
    }
    rows = [row_a, row_b]
    signature = sign_batch(
        table="scrape_logs",
        operation="insert",
        rows=rows,
        locator={},
    )
    assert signature is not None
    assert verify_batch(
        table="scrape_logs",
        operation="insert",
        rows=rows,
        locator={},
        signature=signature,
    )

    tampered_rows = [row_a, {**row_b, "status": "success"}]
    assert not verify_batch(
        table="scrape_logs",
        operation="insert",
        rows=tampered_rows,
        locator={},
        signature=signature,
    )


def test_fail_closed_when_secret_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATA_FIREWALL_SIGNING_SECRET", raising=False)
    reset_signing_settings_cache()

    fields = {"id": "00000000-0000-0000-0000-000000000001", "name": "x"}
    assert (
        sign(
            table="users",
            operation="update",
            fields=fields,
            locator={"id": fields["id"]},
        )
        is None
    )
    assert not verify(
        table="users",
        operation="update",
        fields=fields,
        locator={"id": fields["id"]},
        signature="a" * 64,
    )
    assert (
        sign_batch(
            table="scrape_logs",
            operation="insert",
            rows=[fields],
            locator={},
        )
        is None
    )
    assert not verify_batch(
        table="scrape_logs",
        operation="insert",
        rows=[fields],
        locator={},
        signature="b" * 64,
    )
