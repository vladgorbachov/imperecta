"""Migration 042 — pg_cron fact_price partitions (asyncpg-safe DDL)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_042 = (
    BACKEND_ROOT / "alembic/versions/042_pgcron_fact_price_partitions.py"
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


def test_migration_042_py_compile() -> None:
    ast.parse(MIGRATION_042.read_text(encoding="utf-8"))


def test_migration_042_revision_chain() -> None:
    source = MIGRATION_042.read_text(encoding="utf-8")
    assert 'revision = "042_pgcron_fact_price_partitions"' in source
    assert 'down_revision = "041_grant_imperecta_app_partition_parents"' in source


def test_migration_042_documents_e1_and_rls_app_read() -> None:
    source = MIGRATION_042.read_text(encoding="utf-8")
    assert "E1" in source or "DDL-eviction" in source
    assert "rls_app_read" in source
    assert "_ensure_fact_price_partition" in source
    assert "maintenance.ensure_fact_price_partitions" in source
    assert "ensure-fact-price-partitions" in source
    assert "0 0 * * *" in source


def test_migration_042_has_single_statement_per_op_execute() -> None:
    offenders: list[str] = []
    for sql in _migration_execute_strings(MIGRATION_042):
        if _count_sql_statements(sql) > 1:
            offenders.append(sql.strip()[:120])
    assert offenders == [], f"multi-statement op.execute literals: {offenders}"


def test_alembic_single_head_includes_042() -> None:
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
    assert heads == ["042_pgcron_fact_price_partitions"], f"unexpected heads: {heads}"
    assert (
        revisions["042_pgcron_fact_price_partitions"]
        == "041_grant_imperecta_app_partition_parents"
    )
