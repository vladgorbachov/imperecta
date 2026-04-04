"""Repair alembic_meta.alembic_version, timeouts; optional empty-public reset (idempotent)."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "007_fix_migration_deadlock_and_meta"
down_revision = "006_scrape_logs_status_length"
branch_labels = None
depends_on = None

# Core star-schema tables (dim_* / fact_*) — must all exist before we treat v2 as complete.
_V2_DIM_FACT_TABLES: tuple[str, ...] = (
    "dim_date",
    "dim_currency",
    "dim_country",
    "dim_marketplace",
    "dim_category",
    "dim_brand",
    "dim_product",
    "dim_seller",
    "fact_listing",
    "fact_price",
    "fact_review",
    "fact_stock",
    "fact_search_trend",
    "fact_currency_rate",
    "fact_tariff",
    "fact_promo",
)

_STAMP_IF_DRIFTED = "006_scrape_logs_status_length"


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
    """Patch op.execute to one statement per call (asyncpg)."""
    original_execute = op.execute

    def _safe_execute(statement, *args, **kwargs):
        if isinstance(statement, str):
            for sql in _split_sql_statements(statement):
                original_execute(sql, *args, **kwargs)
            return None
        return original_execute(statement, *args, **kwargs)

    return original_execute, _safe_execute


def _table_exists(bind, schema: str, name: str) -> bool:
    row = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :s AND table_name = :n)"
        ),
        {"s": schema, "n": name},
    ).scalar()
    return row is True


def _public_base_table_count(bind) -> int:
    return int(
        bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        ).scalar()
        or 0
    )


def _all_dim_fact_present(bind) -> bool:
    return all(_table_exists(bind, "public", t) for t in _V2_DIM_FACT_TABLES)


def _alembic_version_empty(bind) -> bool:
    if not _table_exists(bind, "alembic_meta", "alembic_version"):
        return True
    n = bind.execute(
        sa.text("SELECT COUNT(*) FROM alembic_meta.alembic_version")
    ).scalar()
    return int(n or 0) == 0


def _dim_date_exists(bind) -> bool:
    return _table_exists(bind, "public", "dim_date")


_OFFLINE_DO = """
DO $migration_body$
DECLARE
  nver bigint;
  ntbl bigint;
  ddate boolean;
BEGIN
  SET LOCAL lock_timeout = '5s';
  SET LOCAL statement_timeout = '30s';

  CREATE SCHEMA IF NOT EXISTS alembic_meta;

  CREATE TABLE IF NOT EXISTS alembic_meta.alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
  );

  SELECT COUNT(*) INTO nver FROM alembic_meta.alembic_version;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'dim_date'
  ) INTO ddate;

  IF nver = 0 AND ddate THEN
    INSERT INTO alembic_meta.alembic_version (version_num)
    VALUES ('006_scrape_logs_status_length')
    ON CONFLICT DO NOTHING;
    RAISE NOTICE '007 offline: seeded alembic_meta.alembic_version to 006 (drift repair)';
  END IF;

  SELECT COUNT(*) INTO ntbl FROM information_schema.tables
  WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

  IF ntbl = 0 THEN
    DROP SCHEMA IF EXISTS public CASCADE;
    CREATE SCHEMA public;
    GRANT ALL ON SCHEMA public TO PUBLIC;
    GRANT ALL ON SCHEMA public TO postgres;
    RAISE NOTICE '007 offline: empty public — recreated schema public';
  ELSE
    RAISE NOTICE '007 offline: public has tables — skipping DROP SCHEMA public CASCADE';
  END IF;
END
$migration_body$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind is None:
        op.execute(sa.text(_OFFLINE_DO))
        return

    original_execute, _safe_execute = _apply_safe_execute()
    op.execute = _safe_execute
    try:
        op.execute("SET lock_timeout = '5s';")
        op.execute("SET statement_timeout = '30s';")

        op.execute("CREATE SCHEMA IF NOT EXISTS alembic_meta;")
        op.execute(
            """
            CREATE TABLE IF NOT EXISTS alembic_meta.alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            );
            """
        )

        if _alembic_version_empty(bind) and _dim_date_exists(bind):
            op.execute(
                sa.text(
                    "INSERT INTO alembic_meta.alembic_version (version_num) "
                    f"VALUES ('{_STAMP_IF_DRIFTED}') ON CONFLICT DO NOTHING"
                )
            )
            print(
                "WARNING: 007 seeded alembic_meta.alembic_version to "
                f"{_STAMP_IF_DRIFTED} (empty version table, v2 present)"
            )

        if not _all_dim_fact_present(bind):
            ntbl = _public_base_table_count(bind)
            if ntbl == 0:
                op.execute("DROP SCHEMA IF EXISTS public CASCADE;")
                op.execute("CREATE SCHEMA public;")
                op.execute("GRANT ALL ON SCHEMA public TO PUBLIC;")
                op.execute("GRANT ALL ON SCHEMA public TO postgres;")
                print("WARNING: 007 empty public — recreated schema public (no base tables)")
            else:
                print(
                    "WARNING: 007 partial v2 / non-empty public — "
                    "skipping DROP SCHEMA public CASCADE (manual fix may be needed)"
                )
    finally:
        op.execute = original_execute


def downgrade() -> None:
    """No-op: meta repair and optional public reset are not safely reversible here."""
    print("WARNING: 007 downgrade is a no-op (alembic_meta / public reset not reverted)")
