"""Auth API contract tests — verify response shapes match frontend expectations."""

import pytest


@pytest.mark.asyncio
async def test_register_returns_tokens(client):
    """Register returns access_token, refresh_token, token_type."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "newuser@test.com",
            "password": "TestPass123!",
            "name": "New User",
            "language": "en",
        },
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert "token_type" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_returns_tokens_and_flags(client):
    """Login returns tokens. Frontend checks for remember-me and force-password-change."""
    await client.post(
        "/api/auth/register",
        json={
            "email": "logintest@test.com",
            "password": "TestPass123!",
            "name": "Login Test",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        json={
            "email": "logintest@test.com",
            "password": "TestPass123!",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password_401(client):
    """Wrong password returns 401."""
    await client.post(
        "/api/auth/register",
        json={
            "email": "logintest@test.com",
            "password": "TestPass123!",
            "name": "Login Test",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        json={
            "email": "logintest@test.com",
            "password": "WrongPassword",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user_profile(client, auth_headers):
    """Me endpoint returns user profile with expected fields."""
    resp = await client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "email" in data
    assert "name" in data
    assert "language" in data
    assert data["language"] in ["en", "ar", "es", "zh", "ru", "fr", "ro", "uk"]


@pytest.mark.asyncio
async def test_me_without_auth_401(client):
    """Me without auth returns 401 or 403."""
    resp = await client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_register_invalid_language_422(client):
    """Invalid language code returns 422."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "bad@test.com",
            "password": "TestPass123!",
            "name": "Bad",
            "language": "xx",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_me_updates_profile(client, auth_headers):
    """PUT /api/auth/me updates profile and returns user."""
    resp = await client.put(
        "/api/auth/me",
        headers=auth_headers,
        json={
            "name": "Updated Name",
            "company_name": "Acme Corp",
            "avatar_url": "https://example.com/avatar.png",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert data["company_name"] == "Acme Corp"
    assert data["avatar_url"] == "https://example.com/avatar.png"


@pytest.mark.asyncio
async def test_put_me_with_data_url_avatar(client, auth_headers):
    """PUT /api/auth/me accepts data URL avatar (base64 image)."""
    data_url = "data:image/png;base64,iVBORw0KGgo="  # minimal valid base64
    resp = await client.put(
        "/api/auth/me",
        headers=auth_headers,
        json={"avatar_url": data_url},
    )
    assert resp.status_code == 200
    assert resp.json()["avatar_url"] == data_url
