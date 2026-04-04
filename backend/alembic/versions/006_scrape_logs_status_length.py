"""Widen scrape_logs.status to VARCHAR(50) for drifted DBs stuck at VARCHAR(20)."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "006_scrape_logs_status_length"
down_revision = "005_scrape_logs_technical_error"
branch_labels = None
depends_on = None

_TARGET_LEN = 50


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


_UPGRADE_DO = f"""
DO $migration_body$
DECLARE
  dt text;
  clen integer;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'scrape_logs'
  ) THEN
    RAISE WARNING '006 upgrade: public.scrape_logs missing, skipping';
    RETURN;
  END IF;

  SELECT c.data_type, c.character_maximum_length INTO dt, clen
  FROM information_schema.columns c
  WHERE c.table_schema = 'public'
    AND c.table_name = 'scrape_logs'
    AND c.column_name = 'status';

  IF NOT FOUND THEN
    RAISE WARNING '006 upgrade: scrape_logs.status column missing, skipping';
    RETURN;
  END IF;

  IF dt = 'text' OR (clen IS NOT NULL AND clen >= {_TARGET_LEN}) THEN
    RAISE WARNING '006 upgrade: scrape_logs.status already VARCHAR(50+) or TEXT, skipping';
    RETURN;
  END IF;

  ALTER TABLE public.scrape_logs
    ALTER COLUMN status TYPE VARCHAR({_TARGET_LEN});
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
    WHERE table_schema = 'public' AND table_name = 'scrape_logs'
  ) THEN
    RAISE WARNING '006 downgrade: public.scrape_logs missing, skipping';
    RETURN;
  END IF;

  SELECT c.character_maximum_length INTO clen
  FROM information_schema.columns c
  WHERE c.table_schema = 'public'
    AND c.table_name = 'scrape_logs'
    AND c.column_name = 'status'
    AND c.data_type = 'character varying';

  IF NOT FOUND THEN
    RAISE WARNING '006 downgrade: scrape_logs.status not varchar, skipping';
    RETURN;
  END IF;

  IF clen IS NOT NULL AND clen <= 20 THEN
    RAISE WARNING '006 downgrade: scrape_logs.status already VARCHAR(20) or smaller, skipping';
    RETURN;
  END IF;

  ALTER TABLE public.scrape_logs
    ALTER COLUMN status TYPE VARCHAR(20);
END
$migration_body$ LANGUAGE plpgsql;
"""


def _scrape_logs_exists(bind) -> bool:
    row = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'scrape_logs')"
        )
    ).scalar()
    return row is True


def _status_column_meta(bind) -> tuple[str | None, int | None]:
    """Return (data_type, character_maximum_length) for public.scrape_logs.status."""
    row = bind.execute(
        sa.text(
            "SELECT data_type, character_maximum_length "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "AND table_name = 'scrape_logs' "
            "AND column_name = 'status'"
        )
    ).first()
    if row is None:
        return (None, None)
    return (row[0], row[1])


def _apply_safe_execute() -> tuple[object, object]:
    """Patch op.execute to one statement per call (asyncpg)."""
    original_execute = op.execute

    def _safe_execute(statement, *args, **kwargs):
        if isinstance(statement, str):
            for sql in _split_sql_statements(statement):
                original_execute(sql, *args, **kwargs)
            return None
        return original_execute(statement, *args, **kwargs)

    return original_execute, _safe_execute


def upgrade() -> None:
    bind = op.get_bind()
    if bind is None:
        op.execute(sa.text(_UPGRADE_DO))
        return
    if not _scrape_logs_exists(bind):
        print("WARNING: table scrape_logs does not exist yet — skipping 006")
        return

    data_type, char_len = _status_column_meta(bind)
    if data_type is None:
        print("WARNING: scrape_logs.status column missing — skipping 006")
        return
    if data_type == "text" or (char_len is not None and char_len >= _TARGET_LEN):
        print(
            f"WARNING: scrape_logs.status already TEXT or VARCHAR(>={_TARGET_LEN}) — skipping 006"
        )
        return

    original_execute, _safe_execute = _apply_safe_execute()
    op.execute = _safe_execute
    try:
        op.execute(
            f"ALTER TABLE public.scrape_logs ALTER COLUMN status TYPE VARCHAR({_TARGET_LEN});"
        )
    finally:
        op.execute = original_execute


def downgrade() -> None:
    bind = op.get_bind()
    if bind is None:
        op.execute(sa.text(_DOWNGRADE_DO))
        return
    if not _scrape_logs_exists(bind):
        print("WARNING: table scrape_logs does not exist yet — skipping 006 downgrade")
        return

    data_type, char_len = _status_column_meta(bind)
    if data_type is None:
        print("WARNING: scrape_logs.status column missing — skipping 006 downgrade")
        return
    if data_type != "character varying":
        print("WARNING: scrape_logs.status is not character varying — skipping 006 downgrade")
        return
    if char_len is not None and char_len <= 20:
        print("WARNING: scrape_logs.status already VARCHAR(20) or smaller — skipping 006 downgrade")
        return

    original_execute, _safe_execute = _apply_safe_execute()
    op.execute = _safe_execute
    try:
        op.execute("ALTER TABLE public.scrape_logs ALTER COLUMN status TYPE VARCHAR(20);")
    finally:
        op.execute = original_execute
