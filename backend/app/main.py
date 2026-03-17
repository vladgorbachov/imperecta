"""FastAPI application entrypoint."""

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.database import Base, engine
from app.modules.ai_analyst.api import router as ai_router
from app.modules.alerts.api import router as alerts_router
from app.modules.analytics.api import router as analytics_router
from app.modules.core.api_auth import router as auth_router
from app.modules.core.api_telegram import router as telegram_router
from app.modules.dashboard.api import router as dashboard_router
from app.modules.digests.api import router as digests_router
from app.modules.market_data.api import router as market_data_router
from app.modules.marketplaces.api import router as marketplaces_router
from app.modules.product_pool.api import router as pool_router
from app.modules.scraper.api import router as scraper_admin_router
from app.modules.user_products.api_competitors import router as competitors_router
from app.modules.user_products.api_import import router as import_router
from app.modules.user_products.api_products import router as products_router

logger = logging.getLogger(__name__)
settings = Settings()

DEFAULT_JWT_SECRET = "change-me-in-production"
if settings.app_env == "production" and settings.jwt_secret == DEFAULT_JWT_SECRET:
    logger.warning(
        "JWT_SECRET is default value. Set JWT_SECRET in production for security."
    )

if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)


async def _ensure_tables() -> None:
    """Create tables in background so app can accept healthchecks immediately."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        logger.warning("create_all failed (may run later): %s", e)


async def _ensure_superuser() -> None:
    """Create default superuser if none exists. Retries until tables exist."""
    import asyncio

    from app.database import async_session_maker
    from app.modules.core.admin_service import ensure_superuser

    for attempt in range(10):
        try:
            async with async_session_maker() as db:
                await ensure_superuser(db)
            return
        except Exception as e:
            logger.warning("ensure_superuser attempt %s failed: %s", attempt + 1, e)
            await asyncio.sleep(2)
    logger.error("ensure_superuser gave up after 10 attempts")


async def _setup_telegram_webhook() -> None:
    """Set Telegram webhook to receive bot messages."""
    token = settings.telegram_bot_token
    if not token:
        return
    webhook_url = f"{settings.app_url}/api/telegram/webhook"
    api_url = f"https://api.telegram.org/bot{token}/setWebhook"
    payload: dict = {"url": webhook_url}
    if settings.telegram_webhook_secret:
        payload["secret_token"] = settings.telegram_webhook_secret
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(api_url, json=payload)
            data = resp.json()
            if data.get("ok"):
                logger.info("Telegram webhook set: %s", webhook_url)
            else:
                logger.error("Telegram webhook error: %s", data)
    except Exception as e:
        logger.error("Failed to set Telegram webhook: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start app immediately; create DB tables in background for Railway healthcheck."""
    asyncio.create_task(_ensure_tables())
    asyncio.create_task(_setup_telegram_webhook())
    asyncio.create_task(_ensure_superuser())
    yield


app = FastAPI(
    title="Imperecta API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in [
    auth_router,
    telegram_router,
    marketplaces_router,
    scraper_admin_router,
    pool_router,
    market_data_router,
    dashboard_router,
    products_router,
    competitors_router,
    import_router,
    analytics_router,
    alerts_router,
    digests_router,
    ai_router,
]:
    app.include_router(router, prefix="/api")


@app.get("/health")
async def liveness() -> dict:
    """Liveness probe: returns 200 as soon as the process is up (for Railway healthcheck)."""
    return {"status": "ok"}


@app.get("/api/health")
async def health_check() -> dict:
    """Health check endpoint with DB, Redis connectivity and connection pool status."""
    db_ok = False
    redis_ok = False
    db_pool: dict | None = None

    try:
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
        pool = engine.pool
        db_pool = {
            "size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
    except Exception:
        pass

    try:
        import redis

        r = redis.from_url(settings.redis_url)
        r.ping()
        redis_ok = True
    except Exception:
        pass

    result: dict = {
        "status": "ok",
        "db": db_ok,
        "redis": redis_ok,
    }
    if db_pool is not None:
        result["db_pool"] = db_pool
    return result
