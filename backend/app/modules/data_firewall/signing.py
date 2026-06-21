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


def canonical_serialize(record_fields: dict[str, Any]) -> bytes:
    """Deterministic serialization over the exact fields that will be persisted."""
    canonical = {
        key: _canonical_value(record_fields[key])
        for key in sorted(record_fields.keys())
    }
    return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")


def signing_secret() -> str | None:
    """Return the configured signing secret; None means fail-closed."""
    secret = _get_settings().firewall_signing_secret
    if secret is None or not str(secret).strip():
        return None
    return str(secret)


def sign(record_fields: dict[str, Any]) -> str | None:
    """HMAC-SHA256 hex digest over canonical fields; None when secret unset."""
    secret = signing_secret()
    if secret is None:
        return None
    digest = hmac.new(
        secret.encode("utf-8"),
        canonical_serialize(record_fields),
        digestmod="sha256",
    )
    return digest.hexdigest()


def verify(record_fields: dict[str, Any], signature: str | None) -> bool:
    """Constant-time compare of recomputed signature; False when secret or signature missing."""
    if not signature:
        return False
    expected = sign(record_fields)
    if expected is None:
        return False
    return hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class SignedRecord:
    """Firewall-approved payload bound to an HMAC signature."""

    table: str
    fields: dict[str, Any]
    signature: str
