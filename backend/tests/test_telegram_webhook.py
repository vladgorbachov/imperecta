"""Telegram webhook secret validation tests."""

import os
import subprocess
import sys

import pytest


@pytest.mark.asyncio
async def test_webhook_rejects_missing_secret_header(client, monkeypatch):
    """Webhook returns 403 when X-Telegram-Bot-Api-Secret-Token header is missing."""
    monkeypatch.setattr(
        "app.modules.telegram.api.settings",
        type("S", (), {"telegram_webhook_secret": "test-secret-123", "telegram_bot_token": "x"})(),
    )
    resp = await client.post(
        "/api/telegram/webhook",
        json={"message": {"chat": {"id": 1}, "text": "/start"}},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_webhook_rejects_wrong_secret_header(client, monkeypatch):
    """Webhook returns 403 when header value does not match TELEGRAM_WEBHOOK_SECRET."""
    monkeypatch.setattr(
        "app.modules.telegram.api.settings",
        type("S", (), {"telegram_webhook_secret": "test-secret-123", "telegram_bot_token": "x"})(),
    )
    resp = await client.post(
        "/api/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        json={"message": {"chat": {"id": 1}, "text": "/start"}},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_webhook_accepts_valid_secret_header(client, monkeypatch):
    """Webhook accepts request when header matches TELEGRAM_WEBHOOK_SECRET."""
    monkeypatch.setattr(
        "app.modules.telegram.api.settings",
        type("S", (), {"telegram_webhook_secret": "test-secret-123", "telegram_bot_token": "x"})(),
    )
    resp = await client.post(
        "/api/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret-123"},
        json={"message": {"chat": {"id": 1}, "text": "/start"}},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_webhook_rejects_when_no_secret_configured(client, monkeypatch):
    """Webhook returns 403 when TELEGRAM_WEBHOOK_SECRET is not configured."""
    monkeypatch.setattr(
        "app.modules.telegram.api.settings",
        type("S", (), {"telegram_webhook_secret": None, "telegram_bot_token": None})(),
    )
    resp = await client.post(
        "/api/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "any-value"},
        json={"message": {"chat": {"id": 1}, "text": "/start"}},
    )
    assert resp.status_code == 403


def test_config_fails_when_bot_token_set_without_webhook_secret():
    """Settings raises when TELEGRAM_BOT_TOKEN is set but TELEGRAM_WEBHOOK_SECRET is not."""
    env = {k: v for k, v in os.environ.items() if k != "TELEGRAM_WEBHOOK_SECRET"}
    env["TELEGRAM_BOT_TOKEN"] = "test-bot-token"
    result = subprocess.run(
        [sys.executable, "-c", "from app.config import Settings; Settings()"],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    assert result.returncode != 0
    assert "TELEGRAM_WEBHOOK_SECRET" in (result.stderr + result.stdout)
