"""Admin API contract tests — verify superuser-only access."""

import pytest


@pytest.mark.asyncio
async def test_admin_stats_forbidden_for_regular_user(client, auth_headers):
    """Regular user cannot access admin stats."""
    resp = await client.get("/api/admin/stats", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_claude_status_forbidden_for_regular_user(client, auth_headers):
    """Regular user cannot access admin claude-status."""
    resp = await client.get("/api/admin/claude-status", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_ok_for_superuser(client, superuser_headers):
    """Superuser can access admin stats."""
    resp = await client.get("/api/admin/stats", headers=superuser_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "users_count" in data or "marketplaces_count" in data
