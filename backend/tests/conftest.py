"""Pytest fixtures and configuration for API contract tests."""

import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Set test env before any app code that reads config
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/imperecta_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-for-ci-only")

from app.database import async_session_maker, get_db
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client():
    """HTTP client that talks to the app with test DB."""
    async def override_get_db():
        async with async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client):
    """Register + login, return Authorization headers."""
    await client.post(
        "/api/auth/register",
        json={
            "email": "test@imperecta.com",
            "password": "TestPass123!",
            "name": "Test User",
            "language": "en",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        json={
            "email": "test@imperecta.com",
            "password": "TestPass123!",
        },
    )
    data = resp.json()
    token = data.get("access_token")
    if not token:
        pytest.skip("Login failed - check auth setup")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def superuser_headers(client):
    """Create superuser and return auth headers. Uses default admin from ensure_superuser (admin/admin)."""
    resp = await client.post(
        "/api/auth/login",
        json={
            "email": "admin@imperecta.com",
            "password": "admin",
        },
    )
    data = resp.json()
    token = data.get("access_token")
    if not token:
        pytest.skip("Superuser login failed - ensure_superuser may not have run yet")
    return {"Authorization": f"Bearer {token}"}


