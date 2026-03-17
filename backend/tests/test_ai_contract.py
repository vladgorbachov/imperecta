"""AI Chat API contract tests."""

import pytest


@pytest.mark.asyncio
async def test_ai_chat_requires_auth(client):
    """AI chat without auth returns 401 or 403."""
    resp = await client.post("/api/ai/chat", json={"message": "test"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ai_sessions_empty(client, auth_headers):
    """AI sessions returns list (possibly empty)."""
    resp = await client.get("/api/ai/sessions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
