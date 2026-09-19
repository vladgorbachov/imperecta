"""Migration 071 — RU/BY/KZ purge, `maintenance.purge_marketplace`, no regions.

Integration tests against the docker test DB (scripts/run_tests_local.sh):
`alembic upgrade head` replays the chain, then the schema is checked and the
purge routine is exercised on synthetic rows it creates and removes itself.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

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
    return "connection refused" in e or "could not connect" in e or "connect call failed" in e


@pytest.fixture(scope="module")
def migrated_engine():
    proc = subprocess.run(
        _ALEMBIC_UPGRADE_HEAD,
        cwd=BACKEND_ROOT,
        env={**os.environ},
        capture_output=True,
        text=True,
        timeout=600,
    )
    err = (proc.stderr or "") + (proc.stdout or "")
    if proc.returncode != 0 and _pg_unavailable(err):
        pytest.skip(f"Postgres unavailable: {proc.stderr}")
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    engine = create_engine(_sync_database_url())
    yield engine
    engine.dispose()


@pytest.mark.integration
def test_fresh_schema_has_no_purged_countries_or_currencies(migrated_engine) -> None:
    with migrated_engine.connect() as conn:
        countries = conn.execute(
            text("SELECT country_code FROM dim_country WHERE country_code IN ('RU','BY','KZ')")
        ).scalars().all()
        currencies = conn.execute(
            text("SELECT currency_code FROM dim_currency WHERE currency_code IN ('RUB','BYN','KZT')")
        ).scalars().all()
        rates = conn.execute(
            text("SELECT count(*) FROM fact_currency_rate WHERE currency_code IN ('RUB','BYN','KZT')")
        ).scalar_one()
        shops = conn.execute(
            text(
                "SELECT marketplace_code FROM dim_marketplace "
                "WHERE country_code IN ('RU','BY','KZ') OR lower(domain) ~ '\\.(ru|by|kz|su|рф)$'"
            )
        ).scalars().all()
    assert countries == []
    assert currencies == []
    assert rates == 0
    assert shops == []


@pytest.mark.integration
def test_dim_country_has_no_region_columns(migrated_engine) -> None:
    with migrated_engine.connect() as conn:
        cols = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'dim_country' "
                "AND column_name IN ('region', 'subregion')"
            )
        ).scalars().all()
        ck = conn.execute(
            text("SELECT 1 FROM pg_constraint WHERE conname = 'ck_dim_country_region'")
        ).first()
    assert cols == []
    assert ck is None


@pytest.mark.integration
def test_purge_marketplace_routine_removes_everything_and_keeps_shared_products(
    migrated_engine,
) -> None:
    """A marketplace with two listings: one product it alone references
    (goes), one shared with another marketplace (stays, as does the other
    listing and its price row). Dry-run counts first, then the purge."""
    tag = uuid4().hex[:8]
    doomed = uuid4()
    survivor = uuid4()
    p_own, p_shared = uuid4(), uuid4()
    l_own, l_shared, l_other = uuid4(), uuid4(), uuid4()
    with migrated_engine.begin() as conn:
        for mp_id, code in ((doomed, f"doomed_{tag}"), (survivor, f"survivor_{tag}")):
            conn.execute(
                text(
                    "INSERT INTO dim_marketplace (id, marketplace_code, name, source_type, "
                    "country_code, domain, base_url, currency_code) VALUES "
                    "(:id, :code, :code, 'marketplace', 'MD', :domain, :url, 'MDL')"
                ),
                {"id": mp_id, "code": code, "domain": f"{code}.example", "url": f"https://{code}.example"},
            )
        for pid, name in ((p_own, f"own {tag}"), (p_shared, f"shared {tag}")):
            conn.execute(
                text(
                    "INSERT INTO dim_product (id, name, name_normalized, is_active) "
                    "VALUES (:id, :name, :name, true)"
                ),
                {"id": pid, "name": name},
            )
        for lid, pid, mp_id in ((l_own, p_own, doomed), (l_shared, p_shared, doomed), (l_other, p_shared, survivor)):
            conn.execute(
                text(
                    "INSERT INTO fact_listing (id, product_id, marketplace_id, external_url, url_hash, is_active) "
                    "VALUES (:id, :pid, :mp, :url, :hash, true)"
                ),
                {"id": lid, "pid": pid, "mp": mp_id, "url": f"https://x.example/{lid}", "hash": uuid4().hex + uuid4().hex},
            )
        for lid in (l_own, l_shared, l_other):
            conn.execute(
                text(
                    "INSERT INTO fact_price (listing_id, date_id, price, currency_code) "
                    "VALUES (:lid, 20260919, 10.5, 'MDL')"
                ),
                {"lid": lid},
            )
        conn.execute(
            text(
                "INSERT INTO scrape_logs (marketplace_id, listing_id, status, url) "
                "VALUES (:mp, :lid, 'success', :url)"
            ),
            {"mp": doomed, "lid": l_own, "url": f"https://x.example/{l_own}"},
        )

    try:
        with migrated_engine.begin() as conn:
            dry = conn.execute(
                text("SELECT maintenance.purge_marketplace(:id, true)"), {"id": doomed}
            ).scalar_one()
            assert dry["status"] == "dry_run"
            assert dry["listings"] == 2
            assert dry["products"] == 1  # only the un-shared one
            assert dry["prices"] == 2
            assert dry["scrape_logs"] == 1
            still_there = conn.execute(
                text("SELECT count(*) FROM fact_listing WHERE marketplace_id = :id"), {"id": doomed}
            ).scalar_one()
            assert still_there == 2

        with migrated_engine.begin() as conn:
            done = conn.execute(
                text("SELECT maintenance.purge_marketplace(:id, false)"), {"id": doomed}
            ).scalar_one()
            assert done["status"] == "purged"
            assert done["listings"] == 2 and done["products"] == 1 and done["prices"] == 2

        with migrated_engine.connect() as conn:
            assert conn.execute(
                text("SELECT count(*) FROM dim_marketplace WHERE id = :id"), {"id": doomed}
            ).scalar_one() == 0
            assert conn.execute(
                text("SELECT count(*) FROM dim_product WHERE id = :id"), {"id": p_own}
            ).scalar_one() == 0
            assert conn.execute(
                text("SELECT count(*) FROM dim_product WHERE id = :id"), {"id": p_shared}
            ).scalar_one() == 1
            assert conn.execute(
                text("SELECT count(*) FROM fact_listing WHERE id = :id"), {"id": l_other}
            ).scalar_one() == 1
            assert conn.execute(
                text("SELECT count(*) FROM fact_price WHERE listing_id IN (:a, :b)"),
                {"a": l_own, "b": l_shared},
            ).scalar_one() == 0
            assert conn.execute(
                text("SELECT count(*) FROM fact_price WHERE listing_id = :id"), {"id": l_other}
            ).scalar_one() == 1
            again = conn.execute(
                text("SELECT maintenance.purge_marketplace(:id, false)"), {"id": doomed}
            ).scalar_one()
            assert again["status"] == "not_found"
    finally:
        with migrated_engine.begin() as conn:
            conn.execute(text("SELECT maintenance.purge_marketplace(:id, false)"), {"id": survivor})
            conn.execute(text("SELECT maintenance.purge_marketplace(:id, false)"), {"id": doomed})
            conn.execute(
                text("DELETE FROM dim_product WHERE id IN (:a, :b)"), {"a": p_own, "b": p_shared}
            )
