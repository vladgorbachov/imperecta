"""SQLAlchemy async engine and session configuration."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import Settings

settings = Settings()

# Supabase: add SSL and search_path for pooled connections
_connect_args: dict = {}
if "supabase.com" in settings.database_url:
    _connect_args = {"ssl": True, "server_settings": {"search_path": "public"}}

# Pool config: Supabase Pooler (PgBouncer) benefits from LIFO
_engine_kwargs: dict = {
    "echo": settings.debug,
    "pool_size": 5,
    "max_overflow": 10,
    "pool_pre_ping": True,
}
if "supabase.com" in settings.database_url:
    _engine_kwargs["pool_use_lifo"] = True
if _connect_args:
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
