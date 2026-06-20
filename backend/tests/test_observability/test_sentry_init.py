"""Tests for shared Sentry init and mandatory secret scrubbing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.observability import sentry_init as si


def _synthetic_proxy_event() -> dict:
    return {
        "request": {"headers": {"Authorization": "Basic dXNlcjpwYXNz"}},
        "extra": {"proxy_provider_password": "x", "safe_field": "visible"},
        "contexts": {"runtime": {"proxy_provider_username": "user"}},
        "tags": {"decodo_password": "secret"},
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {
                                "vars": {
                                    "auth": "dXNlcjpwYXNz",
                                    "headers": {"Authorization": "Basic dXNlcjpwYXNz"},
                                    "url": "https://example.com",
                                }
                            }
                        ]
                    }
                }
            ]
        },
    }


def test_scrubber_removes_proxy_auth():
    event = _synthetic_proxy_event()
    cleaned = si.scrub_sensitive_event(event)
    assert cleaned is not None
    serialized = str(cleaned)
    assert "dXNlcjpwYXNz" not in serialized
    assert "Basic dXNlcjpwYXNz" not in serialized
    assert cleaned["extra"]["safe_field"] == "visible"
    assert cleaned["extra"]["proxy_provider_password"] == si._REDACTED
    assert cleaned["request"]["headers"]["Authorization"] == si._REDACTED


def test_scrubber_denylist_keys():
    event = {
        "extra": {
            "jwt_secret": "abc",
            "database_url": "postgresql://u:p@host/db",
            "note": "ok",
        },
        "tags": {"api_key": "k"},
    }
    cleaned = si.scrub_sensitive_event(event)
    assert cleaned is not None
    assert cleaned["extra"]["jwt_secret"] == si._REDACTED
    assert cleaned["extra"]["database_url"] == si._REDACTED
    assert cleaned["extra"]["note"] == "ok"
    assert cleaned["tags"]["api_key"] == si._REDACTED


def test_scrubber_error_drops_event(monkeypatch):
    def boom(_mapping, *, frame_vars):
        raise RuntimeError("scrubber broke")

    monkeypatch.setattr(si, "_scrub_mapping", boom)
    assert si.scrub_sensitive_event({"extra": {"note": "x"}}) is None


@patch("app.observability.sentry_init.sentry_sdk")
def test_init_sentry_idempotent(mock_sdk):
    mock_sdk.is_initialized.return_value = True
    si.init_sentry(with_celery=False)
    mock_sdk.init.assert_not_called()


@patch("app.observability.sentry_init.Settings")
@patch("app.observability.sentry_init.sentry_sdk")
def test_init_sentry_noop_without_dsn(mock_sdk, mock_settings_cls):
    mock_sdk.is_initialized.return_value = False
    mock_settings_cls.return_value = MagicMock(sentry_dsn=None)
    si.init_sentry(with_celery=True)
    mock_sdk.init.assert_not_called()


@patch("app.observability.sentry_init.Settings")
@patch("app.observability.sentry_init.sentry_sdk")
def test_init_sentry_with_dsn_and_celery(mock_sdk, mock_settings_cls):
    mock_sdk.is_initialized.return_value = False
    mock_settings_cls.return_value = MagicMock(
        sentry_dsn="https://example@o0.ingest.sentry.io/0",
        app_env="test",
    )
    mock_celery_integration = MagicMock()
    with patch(
        "app.observability.sentry_init.CeleryIntegration",
        return_value=mock_celery_integration,
    ):
        si.init_sentry(with_celery=True)
    mock_sdk.init.assert_called_once()
    kwargs = mock_sdk.init.call_args.kwargs
    assert kwargs["send_default_pii"] is False
    assert kwargs["before_send"] is si.scrub_sensitive_event
    assert mock_celery_integration in kwargs["integrations"]


@patch("app.observability.sentry_init.sentry_sdk")
def test_capture_exception_if_initialized(mock_sdk):
    mock_sdk.is_initialized.return_value = True
    exc = ValueError("boom")
    si.capture_exception_if_initialized(exc)
    mock_sdk.capture_exception.assert_called_once_with(exc)


@patch("app.observability.sentry_init.sentry_sdk")
def test_capture_exception_skipped_when_not_initialized(mock_sdk):
    mock_sdk.is_initialized.return_value = False
    si.capture_exception_if_initialized(RuntimeError("x"))
    mock_sdk.capture_exception.assert_not_called()
