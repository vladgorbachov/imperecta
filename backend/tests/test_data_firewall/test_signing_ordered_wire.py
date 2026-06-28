"""Variant B ordered-wire canonical — pure Python parity with dict B2 (no DB)."""

from __future__ import annotations

import hmac
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.data_firewall.signing import (
    canonical_serialize_signed_batch_payload,
    canonical_serialize_signed_payload,
)
from app.modules.data_firewall.signing_ordered import (
    canonical_serialize_ordered_batch,
    canonical_serialize_ordered_record,
    field_entry,
    ordered_entries_from_mapping,
)

_SECRET = "unit-test-data-firewall-secret"


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


def _sign_ordered_record(
    *,
    table: str,
    operation: str,
    locator: list[tuple[str, bool, str]],
    fields: list[tuple[str, bool, str]],
) -> str:
    canonical = canonical_serialize_ordered_record(
        table=table,
        operation=operation,
        locator=locator,
        fields=fields,
    )
    return hmac.new(_SECRET.encode("utf-8"), canonical, digestmod="sha256").hexdigest()


def test_ordered_record_matches_dict_b2_all_types() -> None:
    fields = _all_type_fields()
    locator: dict = {}
    ordered_fields = ordered_entries_from_mapping(fields)
    ordered_locator = ordered_entries_from_mapping(locator)
    assert canonical_serialize_ordered_record(
        table="users",
        operation="update",
        locator=ordered_locator,
        fields=ordered_fields,
    ) == canonical_serialize_signed_payload(
        table="users",
        operation="update",
        fields=fields,
        locator=locator,
    )


def test_ordered_batch_matches_dict_b2() -> None:
    rows = [
        {"listing_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "status": "success"},
        {"listing_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "status": "error"},
    ]
    ordered_rows = [ordered_entries_from_mapping(row) for row in rows]
    assert canonical_serialize_ordered_batch(
        table="scrape_logs",
        operation="insert",
        locator=[],
        rows=ordered_rows,
    ) == canonical_serialize_signed_batch_payload(
        table="scrape_logs",
        operation="insert",
        rows=rows,
        locator={},
    )


def test_none_vs_empty_string_differ_in_ordered_wire() -> None:
    null_entry = field_entry("note", None)
    empty_entry = field_entry("note", "")
    assert null_entry != empty_entry
    null_bytes = canonical_serialize_ordered_record(
        table="users",
        operation="update",
        locator=[],
        fields=[null_entry],
    )
    empty_bytes = canonical_serialize_ordered_record(
        table="users",
        operation="update",
        locator=[],
        fields=[empty_entry],
    )
    assert null_bytes != empty_bytes


def test_cyrillic_octet_length_prefix() -> None:
    """UTF-8 byte length must differ from character count for Cyrillic."""
    text = "Привет"
    assert len(text.encode("utf-8")) != len(text)
    entry = field_entry("cyrillic", text)
    canonical = canonical_serialize_ordered_record(
        table="users",
        operation="update",
        locator=[],
        fields=[entry],
    )
    assert b"12:\xd0\x9f\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82" in canonical


@pytest.mark.parametrize(
    ("raw", "expected_fragment"),
    [
        (19.99, b"S5:19.99"),
        ("19.99", b"S5:19.99"),
        (1.2e-07, b"S7:1.2e-07"),
        ('{"a":1}', b'S7:{"a":1}'),
        ('["z","a"]', b'S9:["z","a"]'),
    ],
)
def test_numeric_and_json_strings_as_wire_values(raw: object, expected_fragment: bytes) -> None:
    canonical = canonical_serialize_ordered_record(
        table="users",
        operation="update",
        locator=[],
        fields=[field_entry("v", raw)],
    )
    assert expected_fragment in canonical


def test_multi_key_order_is_sensitive() -> None:
    first = canonical_serialize_ordered_record(
        table="users",
        operation="update",
        locator=[],
        fields=[("a", False, "1"), ("b", False, "2")],
    )
    second = canonical_serialize_ordered_record(
        table="users",
        operation="update",
        locator=[],
        fields=[("b", False, "2"), ("a", False, "1")],
    )
    assert first != second


def test_row_order_is_sensitive_in_batch() -> None:
    row_a = [field_entry("id", "1")]
    row_b = [field_entry("id", "2")]
    forward = canonical_serialize_ordered_batch(
        table="scrape_logs",
        operation="insert",
        locator=[],
        rows=[row_a, row_b],
    )
    reversed_rows = canonical_serialize_ordered_batch(
        table="scrape_logs",
        operation="insert",
        locator=[],
        rows=[row_b, row_a],
    )
    assert forward != reversed_rows


def test_ordered_hmac_hex_matches_runtime_hmac() -> None:
    fields = ordered_entries_from_mapping({"amount": Decimal("12.345"), "count": 42})
    canonical = canonical_serialize_ordered_record(
        table="users",
        operation="update",
        locator=[],
        fields=fields,
    )
    digest = _sign_ordered_record(
        table="users",
        operation="update",
        locator=[],
        fields=fields,
    )
    expected = hmac.new(_SECRET.encode("utf-8"), canonical, digestmod="sha256").hexdigest()
    assert digest == expected