"""Shared Sentry initialization with mandatory secret scrubbing."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration

from app.config import Settings

logger = logging.getLogger(__name__)

_REDACTED = "[redacted]"
_BASIC_AUTH_RE = re.compile(r"Basic\s+[A-Za-z0-9+/=_-]+", re.IGNORECASE)

_DENYLIST_KEY_SUBSTRINGS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "dsn",
    "jwt",
    "database_url",
    "redis_url",
    "proxy_provider_user",
    "proxy_provider_pass",
    "decodo_user",
    "decodo_pass",
    "authorization",
    "bootstrap_admin",
)

_SENSITIVE_FRAME_VAR_NAMES = frozenset(
    {
        "auth",
        "password",
        "token",
        "secret",
        "api_key",
        "apikey",
        "authorization",
        "headers",
    }
)

_SENSITIVE_HEADER_NAMES = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
    }
)


def _key_is_denylisted(key: str) -> bool:
    lowered = key.lower()
    return any(sub in lowered for sub in _DENYLIST_KEY_SUBSTRINGS)


def _contains_basic_auth(value: str) -> bool:
    return bool(_BASIC_AUTH_RE.search(value))


def _scrub_string(value: str) -> str:
    if _contains_basic_auth(value):
        return _REDACTED
    return value


def _scrub_mapping(
    mapping: dict[str, Any],
    *,
    frame_vars: bool,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        key_str = str(key)
        key_lower = key_str.lower()
        if frame_vars and key_lower in _SENSITIVE_FRAME_VAR_NAMES:
            out[key_str] = _REDACTED
            continue
        if not frame_vars and (
            key_lower in _SENSITIVE_HEADER_NAMES or key_lower.startswith("auth")
        ):
            out[key_str] = _REDACTED
            continue
        if _key_is_denylisted(key_str):
            out[key_str] = _REDACTED
            continue
        if isinstance(value, str):
            out[key_str] = _scrub_string(value)
        elif isinstance(value, dict):
            nested_frame_vars = frame_vars and key_lower != "headers"
            out[key_str] = _scrub_mapping(value, frame_vars=nested_frame_vars)
        elif isinstance(value, list):
            out[key_str] = [
                _scrub_string(item) if isinstance(item, str) else item for item in value
            ]
        else:
            out[key_str] = value
    return out


def _scrub_stacktrace(event: dict[str, Any]) -> None:
    exception_values = event.get("exception", {}).get("values", []) or []
    for exc_value in exception_values:
        if not isinstance(exc_value, dict):
            continue
        stacktrace = exc_value.get("stacktrace")
        if not isinstance(stacktrace, dict):
            continue
        frames = stacktrace.get("frames", []) or []
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            vars_dict = frame.get("vars")
            if isinstance(vars_dict, dict):
                frame["vars"] = _scrub_mapping(vars_dict, frame_vars=True)


def scrub_sensitive_event(
    event: dict[str, Any],
    hint: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Redact secrets from a Sentry event before transmission.

    On scrubber failure, drop the event (return None) rather than send unscrubbed.
    """
    _ = hint
    try:
        request = event.get("request")
        if isinstance(request, dict):
            headers = request.get("headers")
            if isinstance(headers, dict):
                request["headers"] = _scrub_mapping(headers, frame_vars=False)

        for section in ("extra", "contexts", "tags"):
            section_data = event.get(section)
            if isinstance(section_data, dict):
                event[section] = _scrub_mapping(section_data, frame_vars=False)

        _scrub_stacktrace(event)
        return event
    except Exception:
        logger.exception("sentry_scrubber_failed_dropping_event")
        return None


def init_sentry(*, with_celery: bool = False) -> None:
    """Initialize Sentry once per process; no-op when DSN is unset."""
    if sentry_sdk.is_initialized():
        return

    settings = Settings()
    if not settings.sentry_dsn:
        return

    integrations: list[Any] = []
    if with_celery:
        integrations.append(CeleryIntegration())

    release = os.getenv("RAILWAY_GIT_COMMIT_SHA") or None

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=release,
        traces_sample_rate=0.1,
        send_default_pii=False,
        before_send=scrub_sensitive_event,
        integrations=integrations,
    )


def capture_exception_if_initialized(exc: BaseException) -> None:
    """Send an exception to Sentry only when the SDK is active in this process."""
    if sentry_sdk.is_initialized():
        sentry_sdk.capture_exception(exc)
