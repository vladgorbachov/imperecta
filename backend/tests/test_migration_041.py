"""Migration 041 — rls_app_read on partitioned parents (asyncpg-safe DDL)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_041 = (
    BACKEND_ROOT / "alembic/versions/041_grant_imperecta_app_partition_parents.py"
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
    if stripped.upper().startswith("DO $$"):
        return 1
    return len([part for part in sql.split(";") if part.strip()])


def test_migration_041_py_compile() -> None:
    ast.parse(MIGRATION_041.read_text(encoding="utf-8"))


def test_migration_041_revision_chain() -> None:
    source = MIGRATION_041.read_text(encoding="utf-8")
    assert 'revision = "041_grant_imperecta_app_partition_parents"' in source
    assert 'down_revision = "040_grant_imperecta_app"' in source


def test_migration_041_covers_partition_parents() -> None:
    source = MIGRATION_041.read_text(encoding="utf-8")
    assert "relkind IN ('r', 'p')" in source
    assert "fact_price" in source or "relkind='p'" in source or "relkind = 'p'" in source


def test_migration_041_has_single_statement_per_op_execute() -> None:
    offenders: list[str] = []
    for sql in _migration_execute_strings(MIGRATION_041):
        if _count_sql_statements(sql) > 1:
            offenders.append(sql.strip()[:120])
    assert offenders == [], f"multi-statement op.execute literals: {offenders}"


def test_alembic_single_head_includes_041() -> None:
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
    assert heads == ["041_grant_imperecta_app_partition_parents"], f"unexpected heads: {heads}"
    assert revisions["041_grant_imperecta_app_partition_parents"] == "040_grant_imperecta_app"
