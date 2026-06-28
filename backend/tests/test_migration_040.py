"""Migration 040 — imperecta_app least-privilege grants (asyncpg-safe DDL)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_040 = BACKEND_ROOT / "alembic/versions/040_grant_imperecta_app.py"

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


def test_migration_040_py_compile() -> None:
    ast.parse(MIGRATION_040.read_text(encoding="utf-8"))


def test_migration_040_revision_chain() -> None:
    source = MIGRATION_040.read_text(encoding="utf-8")
    assert 'revision = "040_grant_imperecta_app"' in source
    assert 'down_revision = "039_gate_security_definer_functions"' in source


def test_migration_040_has_no_multi_statement_op_execute_literals() -> None:
    offenders: list[str] = []
    for sql in _migration_execute_strings(MIGRATION_040):
        if _count_sql_statements(sql) > 1:
            offenders.append(sql.strip()[:120])
    assert offenders == [], f"multi-statement op.execute literals: {offenders}"


def test_migration_040_documents_seam_and_carve_out() -> None:
    source = MIGRATION_040.read_text(encoding="utf-8")
    assert "9.3" in source or "seam 9.3" in source
    assert "reject_data" in source
    assert "rls_app_read" in source
    assert "rls_app_reject_insert" in source
    assert "gate.exec_write" in source
    assert "imperecta_app" in source


def test_alembic_single_head_includes_040() -> None:
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
    assert heads == ["040_grant_imperecta_app"], f"unexpected heads: {heads}"
    assert revisions["040_grant_imperecta_app"] == "039_gate_security_definer_functions"
