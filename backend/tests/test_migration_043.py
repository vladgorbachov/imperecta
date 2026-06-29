"""Migration 043 — pg_cron materialized view refresh (asyncpg-safe DDL)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_043 = (
    BACKEND_ROOT / "alembic/versions/043_pgcron_refresh_mviews.py"
)

_EXECUTE_STRING_RE = re.compile(
    r'op\.execute\(\s*(?:r?"""(.*?)"""|r?\'\'\'(.*?)\'\'\'|"([^"]*)"|\'([^\']*)\')',
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
    stripped = sql.strip()
    if stripped.upper().startswith("DO $$") or stripped.upper().startswith("DO $DO$"):
        return 1
    return len([part for part in sql.split(";") if part.strip()])


def test_migration_043_py_compile() -> None:
    ast.parse(MIGRATION_043.read_text(encoding="utf-8"))


def test_migration_043_revision_chain() -> None:
    source = MIGRATION_043.read_text(encoding="utf-8")
    assert 'revision = "043_pgcron_refresh_mviews"' in source
    assert 'down_revision = "042_pgcron_fact_price_partitions"' in source


def test_migration_043_documents_e2_and_skip_predicate() -> None:
    source = MIGRATION_043.read_text(encoding="utf-8")
    assert "E2" in source or "DDL-eviction" in source
    assert "full_pipeline_test" in source
    assert "mv_daily_price_summary" in source
    assert "mv_marketplace_health" in source
    assert "refresh-materialized-views" in source
    assert "0 * * * *" in source
    assert "64MB" in source


def test_migration_043_has_single_statement_per_op_execute() -> None:
    offenders: list[str] = []
    for sql in _migration_execute_strings(MIGRATION_043):
        if _count_sql_statements(sql) > 1:
            offenders.append(sql.strip()[:120])
    assert offenders == [], f"multi-statement op.execute literals: {offenders}"


def test_alembic_single_head_includes_043() -> None:
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

    referenced = {down for down in revisions.values() if down}
    heads = [rev for rev in revisions if rev not in referenced]
    assert heads == ["043_pgcron_refresh_mviews"], f"unexpected heads: {heads}"
    assert (
        revisions["043_pgcron_refresh_mviews"]
        == "042_pgcron_fact_price_partitions"
    )
