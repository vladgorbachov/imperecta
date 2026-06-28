"""Variant B ordered-string wire canonical (persist → plpgsql gate verifier).

Persist (seam 9.4) sends each field as (key, is_null, val) in a pre-sorted array.
The plpgsql gate concatenates those strings without re-sorting or re-canonicalizing.
"""

from __future__ import annotations

from typing import Any

from app.modules.data_firewall.signing import canonical_str


def _lp_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return str(len(encoded)).encode("ascii") + b":" + encoded


def _val_enc(*, is_null: bool, val: str) -> bytes:
    if is_null:
        return b"N"
    return b"S" + _lp_string(val)


def field_entry(key: str, value: Any) -> tuple[str, bool, str]:
    """One ordered wire field: (key, is_null, canonical string value)."""
    string_value = canonical_str(value)
    if string_value is None:
        return (key, True, "")
    return (key, False, string_value)


def ordered_entries_from_mapping(fields: dict[str, Any]) -> list[tuple[str, bool, str]]:
    """Build persist wire entries with keys sorted by Unicode code point."""
    return [field_entry(key, fields[key]) for key in sorted(fields.keys())]


def dict_enc_ordered(entries: list[tuple[str, bool, str]]) -> bytes:
    """Length-prefixed dict encoding in caller-supplied key order (no re-sort)."""
    parts = [b"D" + str(len(entries)).encode("ascii")]
    for key, is_null, val in entries:
        parts.append(_lp_string(key))
        parts.append(_val_enc(is_null=is_null, val=val))
    return b"".join(parts)


def canonical_serialize_ordered_record(
    *,
    table: str,
    operation: str,
    locator: list[tuple[str, bool, str]],
    fields: list[tuple[str, bool, str]],
) -> bytes:
    """Deterministic B2 record bytes from ordered field arrays."""
    return (
        b"T"
        + _lp_string(table)
        + b"O"
        + _lp_string(operation)
        + b"L"
        + dict_enc_ordered(locator)
        + b"F"
        + dict_enc_ordered(fields)
    )


def canonical_serialize_ordered_batch(
    *,
    table: str,
    operation: str,
    locator: list[tuple[str, bool, str]],
    rows: list[list[tuple[str, bool, str]]],
) -> bytes:
    """Deterministic B2 batch bytes from ordered row field arrays."""
    parts = [
        b"T",
        _lp_string(table),
        b"O",
        _lp_string(operation),
        b"L",
        dict_enc_ordered(locator),
        b"R",
        str(len(rows)).encode("ascii"),
    ]
    for row in rows:
        parts.append(dict_enc_ordered(row))
    return b"".join(parts)
