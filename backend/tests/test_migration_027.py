"""Migration 027 — drop in_stock columns and fact_stock table."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]

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
def test_migration_027_removes_stock_columns_and_fact_stock() -> None:
    """After upgrade head, stock columns and fact_stock are absent."""
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
            fp_in_stock = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND table_name = 'fact_price' "
                    "AND column_name = 'in_stock'"
                )
            ).first()
            fl_last_in_stock = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND table_name = 'fact_listing' "
                    "AND column_name = 'last_in_stock'"
                )
            ).first()
            fact_stock = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' "
                    "AND table_name = 'fact_stock'"
                )
            ).first()
    except OSError as exc:
        pytest.skip(f"Postgres unavailable: {exc}")
    finally:
        engine.dispose()

    assert fp_in_stock is None, "fact_price.in_stock should be dropped"
    assert fl_last_in_stock is None, "fact_listing.last_in_stock should be dropped"
    assert fact_stock is None, "fact_stock table should be dropped"
