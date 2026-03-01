"""FastAPI application entrypoint."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import Settings
from app.database import Base, engine

logger = logging.getLogger(__name__)
settings = Settings()

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start app immediately; create DB tables in background for Railway healthcheck."""
    asyncio.create_task(_ensure_tables())
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

app.include_router(api_router, prefix="/api")


@app.get("/health")
async def liveness() -> dict:
    """Liveness probe: returns 200 as soon as the process is up (for Railway healthcheck)."""
    return {"status": "ok"}


@app.get("/api/health")
async def health_check() -> dict:
    """Health check endpoint with DB and Redis connectivity."""
    db_ok = False
    redis_ok = False

    try:
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    try:
        import redis

        r = redis.from_url(settings.redis_url)
        r.ping()
        redis_ok = True
    except Exception:
        pass

    return {
        "status": "ok",
        "db": db_ok,
        "redis": redis_ok,
    }
