"""Stage 2: provider-neutral config with DECODO_* deprecated env aliases."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.config import Settings
from app.modules.scraper.fetch_backends import ProxyProviderBackend
from app.modules.scraper.proxy_provider_limiter import (
    proxy_provider_bucket_capacity,
    proxy_provider_max_rps,
)


def _base_env(**overrides: str) -> dict[str, str]:
    """Minimal env for Settings construction in isolation tests."""
    env = {
        "DATABASE_URL": "postgresql://u:p@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "JWT_SECRET": "secret",
        "JWT_ALGORITHM": "HS256",
        "JWT_EXPIRATION_MINUTES": "60",
        "JWT_REFRESH_EXPIRATION_DAYS": "7",
        "JWT_REFRESH_EXPIRATION_DAYS_REMEMBER": "30",
        "MARKET_DATA_FOREX_URL": "http://localhost/forex",
        "MARKET_DATA_CRYPTO_URL": "http://localhost/crypto",
        "MARKET_DATA_TIMEOUT_SECONDS": "10",
        "MARKET_DATA_RETRY_ATTEMPTS": "1",
        "CLAUDE_MODEL": "claude-test",
        "EMAIL_FROM": "test@example.com",
        "APP_URL": "http://localhost:8000",
        "PROXY_STICKY_DURATION": "300",
        "PROXY_COUNTRY_ROUTING": "false",
        "ALLOWED_ORIGINS": "http://localhost:5173",
        "APP_ENV": "test",
        "PORT": "8000",
    }
    env.update(overrides)
    return env


def test_decodo_api_url_alias_resolves_to_neutral_field() -> None:
    """DECODO_API_URL-only env (prod path) populates proxy_provider_api_url."""
    env = _base_env(
        DECODO_API_URL="https://legacy-provider.example/v2/",
        DECODO_ENABLED="true",
    )
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
    assert settings.proxy_provider_api_url == "https://legacy-provider.example/v2/"
    assert settings.proxy_provider_enabled is True


def test_proxy_provider_api_url_takes_precedence_over_decodo_alias() -> None:
    """Neutral key wins when both neutral and deprecated env vars are set."""
    env = _base_env(
        PROXY_PROVIDER_API_URL="https://neutral.example/v2/",
        DECODO_API_URL="https://legacy.example/v2/",
        PROXY_PROVIDER_ENABLED="false",
        DECODO_ENABLED="true",
    )
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
    assert settings.proxy_provider_api_url == "https://neutral.example/v2/"
    assert settings.proxy_provider_enabled is False


def test_limiter_rps_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Limiter reads proxy_provider_rps from settings (not a hardcoded constant)."""
    env = _base_env(
        DECODO_API_URL="http://localhost/decodo",
        DECODO_ENABLED="false",
        PROXY_PROVIDER_RPS="5",
    )
    with patch.dict(os.environ, env, clear=True):
        monkeypatch.setattr(
            "app.modules.scraper.proxy_provider_limiter.Settings",
            Settings,
        )
        assert proxy_provider_max_rps() == 5
        assert proxy_provider_bucket_capacity() == 5


def test_proxy_provider_backend_reads_neutral_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """ProxyProviderBackend uses resolved neutral fields (alias path from DECODO_*)."""
    env = _base_env(
        DECODO_API_URL="https://provider.example/v2/",
        DECODO_USERNAME="user",
        DECODO_PASSWORD="pass",
        DECODO_ENABLED="true",
    )
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
    monkeypatch.setattr(
        "app.modules.scraper.fetch_backends.settings",
        settings,
    )
    assert ProxyProviderBackend.is_configured() is True
    assert ProxyProviderBackend.is_enabled() is True
    assert ProxyProviderBackend.api_url() == "https://provider.example/v2/"
