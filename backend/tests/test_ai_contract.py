"""AI Chat API contract tests."""

import pytest


@pytest.mark.asyncio
async def test_ai_chat_requires_auth(client):
    """AI chat without auth returns 401 or 403."""
    resp = await client.post("/api/ai/chat", json={"message": "test"})
    assert resp.status_code in (401, 403)
