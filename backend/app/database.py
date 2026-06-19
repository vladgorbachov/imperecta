"""SQLAlchemy async engine and session configuration."""

import ssl
from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import Settings

settings = Settings()

# Sync URL for Celery workers (psycopg2)
_sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
sync_engine = create_engine(
    _sync_url,
    pool_size=3,
    max_overflow=5,
    pool_pre_ping=True,
)
sync_session_factory = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def is_read_only_sql_error(exc: BaseException) -> bool:
    """True when ``exc`` is a Postgres read-only transaction rejection."""
    seen: set[int] = set()

    def _walk(err: BaseException | None) -> bool:
        if err is None or id(err) in seen:
            return False
        seen.add(id(err))
        if err.__class__.__name__ == "ReadOnlySqlTransaction":
            return True
        pgcode = getattr(err, "pgcode", None) or getattr(err, "sqlstate", None)
        if pgcode == "25006":
            return True
        message = str(err).lower()
        if "read-only transaction" in message:
            return True
        if getattr(err, "__cause__", None) is not None and _walk(err.__cause__):
            return True
        if getattr(err, "orig", None) is not None and _walk(err.orig):
            return True
        return False

    return _walk(exc)


def invalidate_sync_session(db) -> None:
    """Discard a broken sync connection so pool_pre_ping checks out a fresh one."""
    try:
        db.connection().invalidate()
    except Exception:
        try:
            db.invalidate()
        except Exception:
            pass

# Disable asyncpg statement cache for PgBouncer (Supabase pooler) transaction mode.
_connect_args: dict = {
    "statement_cache_size": 0,
    "prepared_statement_cache_size": 0,
}
# Supabase pooler often uses a cert that fails default verification (self-signed in chain).
if "supabase.com" in settings.database_url:
    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE
    _connect_args["ssl"] = _ssl_ctx
    _connect_args["server_settings"] = {"search_path": "public"}

# Pool config: Supabase Pooler (PgBouncer) benefits from LIFO
_engine_kwargs: dict = {
    "echo": settings.debug,
    "pool_size": 5,
    "max_overflow": 10,
    "pool_pre_ping": True,
}
if "supabase.com" in settings.database_url:
    _engine_kwargs["pool_use_lifo"] = True
_engine_kwargs["connect_args"] = _connect_args

engine = create_async_engine(settings.database_url, **_engine_kwargs)
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide async database session for route dependencies."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
