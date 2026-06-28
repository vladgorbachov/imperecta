"""Content-bound HMAC signing for firewall-approved persist payloads.

Byte canonical format (B2) — reference for the future plpgsql SECURITY DEFINER verifier.

Reproduction rules (Python and plpgsql must match byte-for-byte):

1. Operate on UTF-8 bytes. All ``:``-prefixed length prefixes count UTF-8 **byte**
   lengths (plpgsql: ``octet_length``).
2. ``lp(s)`` = ASCII decimal of ``len(s.encode("utf-8"))`` + ``b":"`` + UTF-8 bytes of ``s``.
3. ``canonical_str(v)`` stringifies one value (``None`` → SQL NULL slot, no string).
4. ``val_enc(x)`` = ``b"N"`` when ``canonical_str(x)`` is ``None``; else ``b"S"`` + ``lp(s)``.
5. ``dict_enc(d)`` = ``b"D"`` + ASCII decimal ``len(d)`` + for each key sorted by Unicode
   code point (plpgsql: ``ORDER BY key COLLATE "C"``): ``lp(key)`` + ``val_enc(d[key])``.
6. Record canonical::

       b"T" + lp(table) + b"O" + lp(operation)
       + b"L" + dict_enc(locator) + b"F" + dict_enc(fields)

7. Batch canonical::

       b"T" + lp(table) + b"O" + lp(operation)
       + b"L" + dict_enc(locator)
       + b"R" + ASCII decimal len(rows)
       + for each row in list order: dict_enc(row)

8. Dict/list values: ``json.dumps(v, sort_keys=True, ensure_ascii=False,
   separators=(",", ":"))`` — opaque string for HMAC; cast ``::jsonb`` only after
   signature verification.
9. No whitespace outside JSON strings. No escaping except inside JSON strings.
10. HMAC: ``hmac.new(secret.encode("utf-8"), canonical_bytes, sha256).hexdigest()``
    (lowercase hex). Secret unset → ``sign``/``sign_batch`` return ``None``;
    ``verify``/``verify_batch`` return ``False`` (fail-closed).
"""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.config import Settings

_settings: Settings | None = None


def _get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_signing_settings_cache() -> None:
    """Clear cached settings (tests only)."""
    global _settings
    _settings = None


def canonical_str(value: Any) -> str | None:
    """Map one signed payload value to its canonical string (None = SQL NULL slot)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, float):
        return format(value, ".15g")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    return str(value)


def _lp_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return str(len(encoded)).encode("ascii") + b":" + encoded


def _val_enc(value: Any) -> bytes:
    string_value = canonical_str(value)
    if string_value is None:
        return b"N"
    return b"S" + _lp_string(string_value)


def _dict_enc(mapping: dict[str, Any]) -> bytes:
    parts = [b"D" + str(len(mapping)).encode("ascii")]
    for key in sorted(mapping.keys()):
        parts.append(_lp_string(key))
        parts.append(_val_enc(mapping[key]))
    return b"".join(parts)


def canonical_serialize_signed_payload(
    *,
    table: str,
    operation: str,
    fields: dict[str, Any],
    locator: dict[str, Any],
) -> bytes:
    """Deterministic length-prefixed serialization for table + operation + locator + fields."""
    return (
        b"T"
        + _lp_string(table)
        + b"O"
        + _lp_string(operation)
        + b"L"
        + _dict_enc(locator)
        + b"F"
        + _dict_enc(fields)
    )


def signing_secret() -> str | None:
    """Return the configured signing secret; None means fail-closed."""
    secret = _get_settings().data_firewall_signing_secret
    if secret is None or not str(secret).strip():
        return None
    return str(secret)


def sign(
    *,
    table: str,
    operation: str,
    fields: dict[str, Any],
    locator: dict[str, Any],
) -> str | None:
    """HMAC-SHA256 hex digest over bound table/operation/locator/fields."""
    secret = signing_secret()
    if secret is None:
        return None
    digest = hmac.new(
        secret.encode("utf-8"),
        canonical_serialize_signed_payload(
            table=table,
            operation=operation,
            fields=fields,
            locator=locator,
        ),
        digestmod="sha256",
    )
    return digest.hexdigest()


def verify(
    *,
    table: str,
    operation: str,
    fields: dict[str, Any],
    locator: dict[str, Any],
    signature: str | None,
) -> bool:
    """Constant-time compare of recomputed signature; False when secret or signature missing."""
    if not signature:
        return False
    expected = sign(
        table=table,
        operation=operation,
        fields=fields,
        locator=locator,
    )
    if expected is None:
        return False
    return hmac.compare_digest(expected, signature)


def canonical_serialize_signed_batch_payload(
    *,
    table: str,
    operation: str,
    rows: list[dict[str, Any]],
    locator: dict[str, Any],
) -> bytes:
    """Deterministic length-prefixed serialization for table + operation + locator + row batch."""
    parts = [
        b"T",
        _lp_string(table),
        b"O",
        _lp_string(operation),
        b"L",
        _dict_enc(locator),
        b"R",
        str(len(rows)).encode("ascii"),
    ]
    for row in rows:
        parts.append(_dict_enc(row))
    return b"".join(parts)


def sign_batch(
    *,
    table: str,
    operation: str,
    rows: list[dict[str, Any]],
    locator: dict[str, Any] | None = None,
) -> str | None:
    """HMAC-SHA256 hex digest over a bound batch of rows."""
    secret = signing_secret()
    if secret is None:
        return None
    digest = hmac.new(
        secret.encode("utf-8"),
        canonical_serialize_signed_batch_payload(
            table=table,
            operation=operation,
            rows=rows,
            locator=locator or {},
        ),
        digestmod="sha256",
    )
    return digest.hexdigest()


def verify_batch(
    *,
    table: str,
    operation: str,
    rows: list[dict[str, Any]],
    locator: dict[str, Any] | None = None,
    signature: str | None,
) -> bool:
    """Constant-time compare of recomputed batch signature."""
    if not signature:
        return False
    expected = sign_batch(
        table=table,
        operation=operation,
        rows=rows,
        locator=locator or {},
    )
    if expected is None:
        return False
    return hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class SignedRecord:
    """Firewall-approved payload cryptographically bound to table, operation, and locator."""

    table: str
    operation: str
    locator: dict[str, Any]
    fields: dict[str, Any]
    signature: str


@dataclass(frozen=True)
class SignedBatch:
    """Firewall-approved batch payload bound to table, operation, and empty locator."""

    table: str
    operation: str
    locator: dict[str, Any]
    rows: list[dict[str, Any]]
    signature: str
