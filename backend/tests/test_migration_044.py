"""Migration 044 — widen scrape_logs.status (asyncpg-safe DDL)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_044 = (
    BACKEND_ROOT / "alembic/versions/044_widen_scrape_logs_status.py"
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


def test_migration_044_py_compile() -> None:
    ast.parse(MIGRATION_044.read_text(encoding="utf-8"))


def test_migration_044_revision_chain() -> None:
    source = MIGRATION_044.read_text(encoding="utf-8")
    assert 'revision = "044_widen_scrape_logs_status"' in source
    assert 'down_revision = "043_pgcron_refresh_mviews"' in source


def test_migration_044_documents_drift_fix() -> None:
    source = MIGRATION_044.read_text(encoding="utf-8")
    assert "E3a" in source or "drift" in source.lower()
    assert "VARCHAR(50)" in source
    assert "scrape_logs" in source


def test_migration_044_has_single_statement_per_op_execute() -> None:
    offenders: list[str] = []
    for sql in _migration_execute_strings(MIGRATION_044):
        if _count_sql_statements(sql) > 1:
            offenders.append(sql.strip()[:120])
    assert offenders == [], f"multi-statement op.execute literals: {offenders}"


def test_alembic_single_head_includes_044() -> None:
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
    assert heads == ["044_widen_scrape_logs_status"], f"unexpected heads: {heads}"
    assert (
        revisions["044_widen_scrape_logs_status"]
        == "043_pgcron_refresh_mviews"
    )
