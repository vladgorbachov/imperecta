"""Migration 032 — service_alerts table and alert_class retro-sign."""

from __future__ import annotations

import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_032 = (
    BACKEND_ROOT / "alembic/versions/032_service_alerts_and_alert_class.py"
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


def test_migration_032_has_no_multi_statement_op_execute_literals() -> None:
    """asyncpg rejects multiple commands in one prepared statement."""
    offenders: list[str] = []
    for sql in _migration_execute_strings(MIGRATION_032):
        if _count_sql_statements(sql) > 1:
            offenders.append(sql.strip()[:120])
    assert offenders == [], f"multi-statement op.execute literals: {offenders}"


def test_migration_032_records_maintenance_audit() -> None:
    source = MIGRATION_032.read_text(encoding="utf-8")
    assert "record_maintenance_audit" in source
    assert "_audit_ddl" in source
    upgrade_block = source.split("def downgrade")[0].split("def upgrade")[1]
    assert upgrade_block.count("op.execute(") == 4
    assert upgrade_block.count("_audit_ddl(") == 4
