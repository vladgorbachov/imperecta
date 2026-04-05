"""Widen alembic_meta.alembic_version.version_num to VARCHAR(255) for long revision ids."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "008_fix_alembic_version_length"
down_revision = "007_fix_migration_deadlock_and_meta"
branch_labels = None
depends_on = None

_TARGET_LEN = 255


def _split_sql_statements(sql: str) -> list[str]:
    """Split SQL batch into single statements, preserving quoted sections."""
    statements: list[str] = []
    buffer: list[str] = []
    index = 0
    size = len(sql)
    in_single_quote = False
    in_double_quote = False
    dollar_tag: str | None = None

    while index < size:
        char = sql[index]

        if dollar_tag is not None:
            if sql.startswith(dollar_tag, index):
                buffer.append(dollar_tag)
                index += len(dollar_tag)
                dollar_tag = None
                continue
            buffer.append(char)
            index += 1
            continue

        if in_single_quote:
            buffer.append(char)
            if char == "'":
                if index + 1 < size and sql[index + 1] == "'":
                    buffer.append("'")
                    index += 2
                    continue
                in_single_quote = False
            index += 1
            continue

        if in_double_quote:
            buffer.append(char)
            if char == '"':
                if index + 1 < size and sql[index + 1] == '"':
                    buffer.append('"')
                    index += 2
                    continue
                in_double_quote = False
            index += 1
            continue

        if char == "'":
            in_single_quote = True
            buffer.append(char)
            index += 1
            continue

        if char == '"':
            in_double_quote = True
            buffer.append(char)
            index += 1
            continue

        if char == "$":
            probe = index + 1
            while probe < size and (sql[probe].isalnum() or sql[probe] == "_"):
                probe += 1
            if probe < size and sql[probe] == "$":
                tag = sql[index : probe + 1]
                dollar_tag = tag
                buffer.append(tag)
                index = probe + 1
                continue

        if char == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            index += 1
            continue

        buffer.append(char)
        index += 1

    trailing = "".join(buffer).strip()
    if trailing:
        statements.append(trailing)

    return statements


def _apply_safe_execute() -> tuple[object, object]:
    original_execute = op.execute

    def _safe_execute(statement, *args, **kwargs):
        if isinstance(statement, str):
            for sql in _split_sql_statements(statement):
                original_execute(sql, *args, **kwargs)
            return None
        return original_execute(statement, *args, **kwargs)

    return original_execute, _safe_execute


def _alembic_version_table_exists(bind) -> bool:
    row = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'alembic_meta' AND table_name = 'alembic_version')"
        )
    ).scalar()
    return row is True


def _version_num_length(bind) -> tuple[str | None, int | None]:
    row = bind.execute(
        sa.text(
            "SELECT data_type, character_maximum_length "
            "FROM information_schema.columns "
            "WHERE table_schema = 'alembic_meta' "
            "AND table_name = 'alembic_version' "
            "AND column_name = 'version_num'"
        )
    ).first()
    if row is None:
        return (None, None)
    return (row[0], row[1])


_UPGRADE_DO = f"""
DO $migration_body$
DECLARE
  dt text;
  clen integer;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'alembic_meta' AND table_name = 'alembic_version'
  ) THEN
    RAISE WARNING '008 upgrade: alembic_meta.alembic_version missing, skipping';
    RETURN;
  END IF;

  SELECT c.data_type, c.character_maximum_length INTO dt, clen
  FROM information_schema.columns c
  WHERE c.table_schema = 'alembic_meta'
    AND c.table_name = 'alembic_version'
    AND c.column_name = 'version_num';

  IF NOT FOUND THEN
    RAISE WARNING '008 upgrade: version_num column missing, skipping';
    RETURN;
  END IF;

  IF dt = 'text' OR (clen IS NOT NULL AND clen >= {_TARGET_LEN}) THEN
    RAISE WARNING '008 upgrade: version_num already wide enough, skipping';
    RETURN;
  END IF;

  ALTER TABLE alembic_meta.alembic_version
    ALTER COLUMN version_num TYPE VARCHAR({_TARGET_LEN});
END
$migration_body$ LANGUAGE plpgsql;
"""

_DOWNGRADE_DO = """
DO $migration_body$
DECLARE
  clen integer;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'alembic_meta' AND table_name = 'alembic_version'
  ) THEN
    RAISE WARNING '008 downgrade: alembic_meta.alembic_version missing, skipping';
    RETURN;
  END IF;

  SELECT c.character_maximum_length INTO clen
  FROM information_schema.columns c
  WHERE c.table_schema = 'alembic_meta'
    AND c.table_name = 'alembic_version'
    AND c.column_name = 'version_num'
    AND c.data_type = 'character varying';

  IF NOT FOUND THEN
    RAISE WARNING '008 downgrade: version_num not varchar, skipping';
    RETURN;
  END IF;

  IF clen IS NOT NULL AND clen <= 32 THEN
    RAISE WARNING '008 downgrade: version_num already VARCHAR(32) or smaller, skipping';
    RETURN;
  END IF;

  ALTER TABLE alembic_meta.alembic_version
    ALTER COLUMN version_num TYPE VARCHAR(32);
END
$migration_body$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind is None:
        op.execute(sa.text(_UPGRADE_DO))
        return
    if not _alembic_version_table_exists(bind):
        print("WARNING: alembic_meta.alembic_version missing — skipping 008")
        return

    data_type, char_len = _version_num_length(bind)
    if data_type is None:
        print("WARNING: version_num column missing — skipping 008")
        return
    if data_type == "text" or (char_len is not None and char_len >= _TARGET_LEN):
        print("WARNING: version_num already TEXT or VARCHAR(255+) — skipping 008")
        return

    original_execute, _safe_execute = _apply_safe_execute()
    op.execute = _safe_execute
    try:
        op.execute(
            f"ALTER TABLE alembic_meta.alembic_version "
            f"ALTER COLUMN version_num TYPE VARCHAR({_TARGET_LEN});"
        )
    finally:
        op.execute = original_execute


def downgrade() -> None:
    bind = op.get_bind()
    if bind is None:
        op.execute(sa.text(_DOWNGRADE_DO))
        return
    if not _alembic_version_table_exists(bind):
        print("WARNING: alembic_meta.alembic_version missing — skipping 008 downgrade")
        return

    data_type, char_len = _version_num_length(bind)
    if data_type is None:
        print("WARNING: version_num column missing — skipping 008 downgrade")
        return
    if data_type != "character varying":
        print("WARNING: version_num is not varchar — skipping 008 downgrade")
        return
    if char_len is not None and char_len <= 32:
        print("WARNING: version_num already VARCHAR(32) or smaller — skipping 008 downgrade")
        return

    original_execute, _safe_execute = _apply_safe_execute()
    op.execute = _safe_execute
    try:
        op.execute(
            "ALTER TABLE alembic_meta.alembic_version "
            "ALTER COLUMN version_num TYPE VARCHAR(32);"
        )
    finally:
        op.execute = original_execute
