"""Migration 051 — pool read-path performance (asyncpg-safe DDL)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_051 = BACKEND_ROOT / "alembic/versions/051_pool_read_perf.py"

_EXECUTE_STRING_RE = re.compile(
    r'op\.execute\(\s*(?:r?f?"""(.*?)"""|r?f?\'\'\'(.*?)\'\'\'|"([^"]*)"|\'([^\']*)\')',
    re.DOTALL,
)


def _migration_execute_strings(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    strings: list[str] = []
    for match in _EXECUTE_STRING_RE.finditer(source):
        value = next(group for group in match.groups() if group is not None)
        strings.append(value)
    return strings


def _count_sql_statements(sql: str) -> int:
    stripped = sql.strip().upper()
    if stripped.startswith("DO $$") or stripped.startswith("DO $DO$"):
        return 1
    if stripped.startswith("CREATE OR REPLACE FUNCTION"):
        return 1
    return len([part for part in sql.split(";") if part.strip()])


def test_migration_051_py_compile() -> None:
    ast.parse(MIGRATION_051.read_text(encoding="utf-8"))


def test_migration_051_revision_chain() -> None:
    source = MIGRATION_051.read_text(encoding="utf-8")
    assert 'revision = "051_pool_read_perf"' in source
    assert 'down_revision = "050_service_alerts_update"' in source


def test_migration_051_creates_read_path_objects() -> None:
    source = MIGRATION_051.read_text(encoding="utf-8")
    assert "idx_listing_pool_entry_created" in source
    assert "idx_listing_active_priced" in source
    assert "idx_fact_price_listing_date_scraped" in source
    assert "mv_pool_stats" in source
    assert "REFRESH MATERIALIZED VIEW CONCURRENTLY" in source
    assert "refresh-pool-stats" in source
    assert "*/10 * * * *" in source
    # CONCURRENTLY refresh requires a unique index on the view.
    assert "idx_mv_pool_stats_singleton" in source


def test_migration_051_partial_indexes_match_pool_grain() -> None:
    source = MIGRATION_051.read_text(encoding="utf-8")
    assert "WHERE is_active = TRUE AND page_role = 'product'" in source
    assert "WHERE is_active = TRUE AND last_price IS NOT NULL" in source


def test_migration_051_index_builds_are_plain_in_transaction() -> None:
    """CONCURRENTLY + autocommit_block is impossible in this project's alembic
    env (async engine bridge; alembic never owns a committable transaction —
    AssertionError on deploys e592d972/7fa6e57e/80094a3e, 2026-09-18). Index
    builds must be plain in-transaction CREATE INDEX with a raised
    statement_timeout: env.py's default is too tight for 1.4M-row builds."""
    source = MIGRATION_051.read_text(encoding="utf-8")
    # The docstring may mention autocommit_block as the forbidden variant;
    # the code must not call it.
    assert "op.get_context().autocommit_block()" not in source
    assert "CREATE INDEX CONCURRENTLY" not in source
    assert "SET LOCAL statement_timeout = '600s'" in source
    assert (
        "CREATE INDEX IF NOT EXISTS idx_listing_pool_entry_created" in source
    )
    assert "CREATE INDEX IF NOT EXISTS idx_listing_active_priced" in source
    # New fact_price index must be created before the superseded one is dropped.
    assert source.index("idx_fact_price_listing_date_scraped") < source.index(
        "DROP INDEX IF EXISTS idx_fact_price_listing_date"
    )


def test_migration_051_hardens_and_grants_mv() -> None:
    source = MIGRATION_051.read_text(encoding="utf-8")
    assert "REVOKE ALL ON public.mv_pool_stats FROM anon, authenticated" in source
    assert "GRANT SELECT ON public.mv_pool_stats TO imperecta_app" in source


def test_migration_051_schedules_bare_concurrent_refresh() -> None:
    """REFRESH ... CONCURRENTLY cannot run inside a function/transaction block,
    so the pg_cron command must be the bare statement (unlike 043's wrapper)."""
    source = MIGRATION_051.read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION" not in source
    assert (
        "'REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_pool_stats'" in source
    )


def test_migration_051_has_single_statement_per_op_execute() -> None:
    offenders: list[str] = []
    for sql in _migration_execute_strings(MIGRATION_051):
        if _count_sql_statements(sql) > 1:
            offenders.append(sql.strip()[:120])
    assert offenders == [], f"multi-statement op.execute literals: {offenders}"


def test_alembic_chain_includes_051() -> None:
    versions_dir = BACKEND_ROOT / "alembic" / "versions"
    revisions: dict[str, str | None] = {}
    for path in versions_dir.glob("*.py"):
        if path.name.startswith("__"):
            continue
        source = path.read_text(encoding="utf-8")
        rev_match = re.search(r'^revision\s*=\s*"([^"]+)"', source, re.MULTILINE)
        down_match = re.search(r'^down_revision\s*=\s*"([^"]+)"', source, re.MULTILINE)
        if rev_match is None:
            continue
        revisions[rev_match.group(1)] = down_match.group(1) if down_match else None

    assert revisions["051_pool_read_perf"] == "050_service_alerts_update"
