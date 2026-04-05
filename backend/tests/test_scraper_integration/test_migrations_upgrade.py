"""Apply Alembic migrations on test DB (integration)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[2]

_ALEMBIC_UPGRADE_HEAD = [sys.executable, "-m", "alembic", "upgrade", "head"]


def _sync_database_url() -> str:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/imperecta_test",
    )
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _pg_unavailable(err: str) -> bool:
    e = err.lower()
    return (
        "connection refused" in e
        or "could not connect" in e
        or "connect call failed" in e
    )


@pytest.mark.integration
def test_alembic_upgrade_head():
    """Run `alembic upgrade head` against DATABASE_URL (local Postgres test DB)."""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/imperecta_test",
    )
    env = {**os.environ, "DATABASE_URL": url}
    proc = subprocess.run(
        _ALEMBIC_UPGRADE_HEAD,
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    err = (proc.stderr or "") + (proc.stdout or "")
    if proc.returncode != 0 and _pg_unavailable(err):
        pytest.skip(f"Postgres unavailable: {proc.stderr}")
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"


@pytest.mark.integration
def test_scrape_logs_status_column_at_least_varchar_50():
    """After migrations, scrape_logs.status must fit longest CHECK values (e.g. VARCHAR(50))."""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/imperecta_test",
    )
    env = {**os.environ, "DATABASE_URL": url}
    proc = subprocess.run(
        _ALEMBIC_UPGRADE_HEAD,
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    err = (proc.stderr or "") + (proc.stdout or "")
    if proc.returncode != 0 and _pg_unavailable(err):
        pytest.skip(f"Postgres unavailable: {proc.stderr}")
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"

    sync_url = _sync_database_url()
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT data_type, character_maximum_length "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND table_name = 'scrape_logs' "
                    "AND column_name = 'status'"
                )
            ).first()
    except OSError as exc:
        pytest.skip(f"Postgres unavailable: {exc}")
    finally:
        engine.dispose()

    assert row is not None, "scrape_logs.status column should exist after migrations"
    data_type, char_len = row[0], row[1]
    assert data_type == "text" or (
        char_len is not None and char_len >= 50
    ), f"expected TEXT or VARCHAR(50+), got {data_type!r} len={char_len!r}"


@pytest.mark.integration
def test_alembic_version_num_at_least_varchar_255():
    """alembic_meta.alembic_version.version_num must fit long revision ids (migration 008)."""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/imperecta_test",
    )
    env = {**os.environ, "DATABASE_URL": url}
    proc = subprocess.run(
        _ALEMBIC_UPGRADE_HEAD,
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    err = (proc.stderr or "") + (proc.stdout or "")
    if proc.returncode != 0 and _pg_unavailable(err):
        pytest.skip(f"Postgres unavailable: {proc.stderr}")
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"

    sync_url = _sync_database_url()
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT data_type, character_maximum_length "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'alembic_meta' "
                    "AND table_name = 'alembic_version' "
                    "AND column_name = 'version_num'"
                )
            ).first()
    except OSError as exc:
        pytest.skip(f"Postgres unavailable: {exc}")
    finally:
        engine.dispose()

    assert row is not None, "alembic_meta.alembic_version.version_num should exist"
    data_type, char_len = row[0], row[1]
    assert data_type == "text" or (
        char_len is not None and char_len >= 255
    ), f"expected TEXT or VARCHAR(255+), got {data_type!r} len={char_len!r}"


@pytest.mark.integration
def test_migration_chain_idempotent_no_deadlock():
    """Running `alembic upgrade head` twice must succeed (idempotent chain, no deadlock)."""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/imperecta_test",
    )
    env = {**os.environ, "DATABASE_URL": url}
    for run in (1, 2):
        proc = subprocess.run(
            _ALEMBIC_UPGRADE_HEAD,
            cwd=BACKEND_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        err = (proc.stderr or "") + (proc.stdout or "")
        if proc.returncode != 0 and _pg_unavailable(err):
            pytest.skip(f"Postgres unavailable: {proc.stderr}")
        assert proc.returncode == 0, (
            f"run {run}: {proc.stdout}\n{proc.stderr}"
        )
