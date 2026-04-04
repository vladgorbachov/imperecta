"""Add technical_error to scrape_logs.status CHECK (idempotent if table missing)."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "005_scrape_logs_technical_error"
down_revision = "004_fix_real_state"
branch_labels = None
depends_on = None


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


# Single PL/pgSQL block for offline SQL generation / when get_bind() is unavailable.
_UPGRADE_DO = """
DO $migration_body$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name = 'scrape_logs'
  ) THEN
    ALTER TABLE public.scrape_logs DROP CONSTRAINT IF EXISTS ck_scrape_logs_status;
    ALTER TABLE public.scrape_logs ADD CONSTRAINT ck_scrape_logs_status CHECK (
      status IN (
        'success','error','timeout','blocked','captcha',
        'not_found','price_not_found','parse_error','missing_critical_data',
        'technical_error'
      )
    );
  ELSE
    RAISE WARNING '005_scrape_logs_technical_error upgrade: public.scrape_logs missing, skipping';
  END IF;
END
$migration_body$ LANGUAGE plpgsql;
"""

_DOWNGRADE_DO = """
DO $migration_body$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name = 'scrape_logs'
  ) THEN
    ALTER TABLE public.scrape_logs DROP CONSTRAINT IF EXISTS ck_scrape_logs_status;
    ALTER TABLE public.scrape_logs ADD CONSTRAINT ck_scrape_logs_status CHECK (
      status IN (
        'success','error','timeout','blocked','captcha',
        'not_found','price_not_found','parse_error','missing_critical_data'
      )
    );
  ELSE
    RAISE WARNING '005_scrape_logs_technical_error downgrade: public.scrape_logs missing, skipping';
  END IF;
END
$migration_body$ LANGUAGE plpgsql;
"""

_CHECK_ADD_UPGRADE = sa.text(
    "ALTER TABLE public.scrape_logs ADD CONSTRAINT ck_scrape_logs_status CHECK (status IN ("
    "'success','error','timeout','blocked','captcha',"
    "'not_found','price_not_found','parse_error','missing_critical_data',"
    "'technical_error'"
    "))"
)

_CHECK_ADD_DOWNGRADE = sa.text(
    "ALTER TABLE public.scrape_logs ADD CONSTRAINT ck_scrape_logs_status CHECK (status IN ("
    "'success','error','timeout','blocked','captcha',"
    "'not_found','price_not_found','parse_error','missing_critical_data'"
    "))"
)


def _scrape_logs_exists(bind) -> bool:
    """Return True when public.scrape_logs exists (handles drifted Supabase)."""
    row = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'scrape_logs')"
        )
    ).scalar()
    return row is True


def _apply_safe_execute() -> tuple[object, object]:
    """Patch op.execute to one statement per call (asyncpg). Returns (original, _safe_execute)."""
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
        print("WARNING: table scrape_logs does not exist yet — skipping 005")
        return

    original_execute, _safe_execute = _apply_safe_execute()
    op.execute = _safe_execute
    try:
        op.execute(
            "ALTER TABLE public.scrape_logs DROP CONSTRAINT IF EXISTS ck_scrape_logs_status;"
        )
        op.execute(_CHECK_ADD_UPGRADE)
    finally:
        op.execute = original_execute


def downgrade() -> None:
    bind = op.get_bind()
    if bind is None:
        op.execute(sa.text(_DOWNGRADE_DO))
        return
    if not _scrape_logs_exists(bind):
        print("WARNING: table scrape_logs does not exist yet — skipping 005")
        return

    original_execute, _safe_execute = _apply_safe_execute()
    op.execute = _safe_execute
    try:
        op.execute(
            "ALTER TABLE public.scrape_logs DROP CONSTRAINT IF EXISTS ck_scrape_logs_status;"
        )
        op.execute(_CHECK_ADD_DOWNGRADE)
    finally:
        op.execute = original_execute
