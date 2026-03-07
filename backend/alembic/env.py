"""Alembic environment configuration for async SQLAlchemy."""

import asyncio
import os
import ssl
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from app.database import Base
from app.models import (
    AdminMarketplace,
    AIChatMessage,
    AIChatSession,
    ApiLog,
    Alert,
    AlertEvent,
    Competitor,
    CompetitorProduct,
    Digest,
    PriceSnapshot,
    Product,
    ScrapeLog,
    User,
)

config = context.config

# Override sqlalchemy.url from environment variable (keep asyncpg for async migrations)
database_url = os.getenv("DATABASE_URL", "")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with given connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    from sqlalchemy.ext.asyncio import create_async_engine

    url = database_url or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("DATABASE_URL or sqlalchemy.url must be set")

    # Supabase pooler: same SSL context as app/database.py (skip verify for self-signed chain)
    connect_args = {}
    if "supabase.com" in url:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args = {"ssl": ssl_ctx, "server_settings": {"search_path": "public"}}

    connectable = create_async_engine(
        url, poolclass=pool.NullPool, connect_args=connect_args
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
