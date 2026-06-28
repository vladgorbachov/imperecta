"""Migration 039 — gate SECURITY DEFINER functions (asyncpg-safe DDL)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_039 = (
    BACKEND_ROOT / "alembic/versions/039_gate_security_definer_functions.py"
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
    return len([part for part in sql.split(";") if part.strip()])


def test_migration_039_py_compile() -> None:
    source = MIGRATION_039.read_text(encoding="utf-8")
    ast.parse(source)


def test_migration_039_revision_chain() -> None:
    source = MIGRATION_039.read_text(encoding="utf-8")
    assert 'revision = "039_gate_security_definer_functions"' in source
    assert 'down_revision = "038_create_imperecta_app_role"' in source


_CREATE_STRING_RE = re.compile(
    r'_create\(\s*(?:r?"""(.*?)"""|r?\'\'\'(.*?)\'\'\')\s*\)',
    re.DOTALL,
)


def _migration_sql_literals(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    strings: list[str] = []
    for pattern in (_EXECUTE_STRING_RE, _CREATE_STRING_RE):
        for match in pattern.finditer(source):
            value = next(group for group in match.groups() if group is not None)
            strings.append(value)
    return strings


def test_migration_039_has_no_multi_statement_op_execute_literals() -> None:
    offenders: list[str] = []
    for sql in _migration_sql_literals(MIGRATION_039):
        if _count_sql_statements(sql) > 1:
            offenders.append(sql.strip()[:120])
    assert offenders == [], f"multi-statement op.execute literals: {offenders}"


def test_migration_039_documents_idle_seam_and_vault_prerequisite() -> None:
    source = MIGRATION_039.read_text(encoding="utf-8")
    assert "9.2" in source
    assert "data_firewall_signing_secret" in source
    assert "REVOKE EXECUTE" in source or "_revoke" in source
    assert "gate.exec_write" in source
    assert "gate._canonical_record" in source


def test_alembic_single_head_includes_039() -> None:
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
    assert heads == ["039_gate_security_definer_functions"], f"unexpected heads: {heads}"
    assert revisions["039_gate_security_definer_functions"] == "038_create_imperecta_app_role"
