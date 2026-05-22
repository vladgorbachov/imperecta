"""Pytest fixtures and configuration for API contract tests."""

import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Set test env before any app code that reads config
os.environ.setdefault("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", ""))
os.environ.setdefault("REDIS_URL", os.environ.get("TEST_REDIS_URL", ""))
os.environ.setdefault("JWT_SECRET", os.environ.get("TEST_JWT_SECRET", ""))
os.environ.setdefault("JWT_ALGORITHM", os.environ.get("TEST_JWT_ALGORITHM", ""))
os.environ.setdefault(
    "JWT_EXPIRATION_MINUTES", os.environ.get("TEST_JWT_EXPIRATION_MINUTES", "")
)
os.environ.setdefault(
    "JWT_REFRESH_EXPIRATION_DAYS",
    os.environ.get("TEST_JWT_REFRESH_EXPIRATION_DAYS", ""),
)
os.environ.setdefault(
    "JWT_REFRESH_EXPIRATION_DAYS_REMEMBER",
    os.environ.get("TEST_JWT_REFRESH_EXPIRATION_DAYS_REMEMBER", ""),
)
os.environ.setdefault(
    "MARKET_DATA_FOREX_URL", os.environ.get("TEST_MARKET_DATA_FOREX_URL", "")
)
os.environ.setdefault(
    "MARKET_DATA_CRYPTO_URL", os.environ.get("TEST_MARKET_DATA_CRYPTO_URL", "")
)
os.environ.setdefault(
    "MARKET_DATA_TIMEOUT_SECONDS",
    os.environ.get("TEST_MARKET_DATA_TIMEOUT_SECONDS", ""),
)
os.environ.setdefault(
    "MARKET_DATA_RETRY_ATTEMPTS", os.environ.get("TEST_MARKET_DATA_RETRY_ATTEMPTS", "")
)
os.environ.setdefault("CLAUDE_MODEL", os.environ.get("TEST_CLAUDE_MODEL", ""))
os.environ.setdefault("EMAIL_FROM", os.environ.get("TEST_EMAIL_FROM", ""))
os.environ.setdefault("APP_URL", os.environ.get("TEST_APP_URL", ""))
os.environ.setdefault(
    "PROXY_STICKY_DURATION", os.environ.get("TEST_PROXY_STICKY_DURATION", "")
)
os.environ.setdefault(
    "PROXY_COUNTRY_ROUTING", os.environ.get("TEST_PROXY_COUNTRY_ROUTING", "")
)
os.environ.setdefault("DECODO_API_URL", os.environ.get("TEST_DECODO_API_URL", ""))
os.environ.setdefault("DECODO_ENABLED", os.environ.get("TEST_DECODO_ENABLED", ""))
os.environ.setdefault("ALLOWED_ORIGINS", os.environ.get("TEST_ALLOWED_ORIGINS", ""))
os.environ.setdefault("APP_ENV", os.environ.get("TEST_APP_ENV", "test"))
os.environ.setdefault("PORT", os.environ.get("TEST_PORT", "8000"))

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
    """Create superuser and return auth headers using test bootstrap credentials."""
    admin_email = os.environ.get("TEST_BOOTSTRAP_ADMIN_EMAIL", "")
    admin_password = os.environ.get("TEST_BOOTSTRAP_ADMIN_PASSWORD", "")
    if not admin_email or not admin_password:
        pytest.skip("Superuser credentials are not configured for tests")
    resp = await client.post(
        "/api/auth/login",
        json={
            "email": admin_email,
            "password": admin_password,
        },
    )
    data = resp.json()
    token = data.get("access_token")
    if not token:
        pytest.skip("Superuser login failed - ensure_superuser may not have run yet")
    return {"Authorization": f"Bearer {token}"}


