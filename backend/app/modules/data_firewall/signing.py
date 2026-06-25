"""Content-bound HMAC signing for firewall-approved persist payloads."""

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


def _canonical_value(value: Any) -> Any:
    """Stable JSON-serializable representation for one field value."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return format(value, ".15g")
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str):
        return value
    return str(value)


def _canonical_field_dict(record_fields: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _canonical_value(record_fields[key])
        for key in sorted(record_fields.keys())
    }


def canonical_serialize(record_fields: dict[str, Any]) -> bytes:
    """Deterministic serialization over a field dict (legacy helper for tests)."""
    return json.dumps(
        _canonical_field_dict(record_fields),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_serialize_signed_payload(
    *,
    table: str,
    operation: str,
    fields: dict[str, Any],
    locator: dict[str, Any],
) -> bytes:
    """Deterministic serialization for table + operation + locator + fields."""
    canonical = {
        "__table__": table,
        "__operation__": operation,
        "__locator__": _canonical_field_dict(locator),
        "fields": _canonical_field_dict(fields),
    }
    return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")


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


@dataclass(frozen=True)
class SignedRecord:
    """Firewall-approved payload cryptographically bound to table, operation, and locator."""

    table: str
    operation: str
    locator: dict[str, Any]
    fields: dict[str, Any]
    signature: str
