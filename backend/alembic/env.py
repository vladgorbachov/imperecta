"""Alembic environment configuration for async SQLAlchemy."""

import asyncio
import os
import ssl
from logging.config import fileConfig
from uuid import uuid4

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection

from alembic import context
from app.database import Base
from app.models import *  # noqa: F401,F403 — loads all models into Base.metadata

config = context.config

# Override sqlalchemy.url from environment variable (keep asyncpg for async migrations)
database_url = os.getenv("DATABASE_URL", "")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Drift repair: stamp when v2 exists but alembic_version was lost (before full chain).
_STAMP_DRIFT_REVISION = "008_fix_alembic_version_length"


def render_item(type_, obj, autogen_context):
    """Autogenerate hook: keep default rendering for stable schema comparison."""
    return False


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="alembic_meta",
        compare_type=True,
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with v2 schema detection, drift repair, and auto-reset."""
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS alembic_meta"))
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS alembic_meta.alembic_version (
                version_num VARCHAR(255) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            )
            """
        )
    )

    v2_applied = connection.execute(
        text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables "
            "  WHERE table_schema = 'public' AND table_name = 'dim_date'"
            ")"
        )
    ).scalar()

    version_table_exists = connection.execute(
        text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables "
            "  WHERE table_schema = 'alembic_meta' AND table_name = 'alembic_version'"
            ")"
        )
    ).scalar()

    if version_table_exists and not v2_applied:
        connection.execute(text("DELETE FROM alembic_meta.alembic_version"))

    nver = connection.execute(text("SELECT COUNT(*) FROM alembic_meta.alembic_version")).scalar()
    if v2_applied and int(nver or 0) == 0:
        connection.execute(
            text(
                "INSERT INTO alembic_meta.alembic_version (version_num) "
                f"VALUES ('{_STAMP_DRIFT_REVISION}') ON CONFLICT DO NOTHING"
            )
        )

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema="alembic_meta",
        compare_type=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    from sqlalchemy.ext.asyncio import create_async_engine

    url = database_url or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("DATABASE_URL or sqlalchemy.url must be set")

    # Supabase pooler (PgBouncer): add params to URL so they reach asyncpg
    if "supabase.com" in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}prepared_statement_cache_size=0&statement_cache_size=0"

    # Supabase pooler (PgBouncer): use unique prepared statement names to avoid conflicts
    connect_args: dict = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    }
    session_settings = {
        "lock_timeout": "10s",
        "statement_timeout": "60s",
    }
    if "supabase.com" in url:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx
        connect_args["server_settings"] = {
            **session_settings,
            "search_path": "public",
        }
    else:
        connect_args["server_settings"] = dict(session_settings)

    connectable = create_async_engine(
        url, poolclass=pool.NullPool, connect_args=connect_args
    )

    async with connectable.connect() as connection:
        # Create schema before sync callback so version_table_schema is valid on first run.
        await connection.execute(text("CREATE SCHEMA IF NOT EXISTS alembic_meta"))
        await connection.commit()
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
