"""plpgsql gate._canonical_* byte parity vs Python ordered-wire (requires Postgres).

Marked ``integration``: skipped when DATABASE_URL is unreachable or migration 039
is not applied. Safe in CI sandbox without a database.
"""

from __future__ import annotations

import hmac
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine, text

from app.modules.data_firewall.signing_ordered import (
    canonical_serialize_ordered_batch,
    canonical_serialize_ordered_record,
    field_entry,
    ordered_entries_from_mapping,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_UPGRADE_HEAD = [sys.executable, "-m", "alembic", "upgrade", "head"]


def _sync_database_url() -> str:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/imperecta_test",
    )
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _pg_unavailable(err: str) -> bool:
    e = err.lower()
    return (
        "connection refused" in e
        or "could not connect" in e
        or "connect call failed" in e
    )


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _pg_field_entries(entries: list[tuple[str, bool, str]]) -> str:
    if not entries:
        return "ARRAY[]::gate.field_entry[]"
    parts: list[str] = []
    for key, is_null, val in entries:
        parts.append(
            f"ROW({_sql_literal(key)}, {str(is_null).lower()}, {_sql_literal(val)})::gate.field_entry"
        )
    return "ARRAY[" + ", ".join(parts) + "]::gate.field_entry[]"


def _pg_row_payloads(rows: list[list[tuple[str, bool, str]]]) -> str:
    if not rows:
        return "ARRAY[]::gate.row_payload[]"
    parts: list[str] = []
    for row in rows:
        parts.append(f"ROW({_pg_field_entries(row)})::gate.row_payload")
    return "ARRAY[" + ", ".join(parts) + "]::gate.row_payload[]"


def _ensure_migrations() -> None:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/imperecta_test",
    )
    env = {**os.environ, "DATABASE_URL": url}
    proc = subprocess.run(
        _ALEMBIC_UPGRADE_HEAD,
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    err = (proc.stderr or "") + (proc.stdout or "")
    if proc.returncode != 0 and _pg_unavailable(err):
        pytest.skip(f"Postgres unavailable: {proc.stderr}")
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"


def _gate_record_bytes(
    conn,
    *,
    table: str,
    operation: str,
    locator: list[tuple[str, bool, str]],
    fields: list[tuple[str, bool, str]],
) -> bytes:
    sql = (
        "SELECT gate._canonical_record("
        f"{_sql_literal(table)}, "
        f"{_sql_literal(operation)}, "
        f"{_pg_field_entries(locator)}, "
        f"{_pg_field_entries(fields)}"
        ")"
    )
    row = conn.execute(text(sql)).one()
    return bytes(row[0])


def _gate_batch_bytes(
    conn,
    *,
    table: str,
    operation: str,
    locator: list[tuple[str, bool, str]],
    rows: list[list[tuple[str, bool, str]]],
) -> bytes:
    sql = (
        "SELECT gate._canonical_batch("
        f"{_sql_literal(table)}, "
        f"{_sql_literal(operation)}, "
        f"{_pg_field_entries(locator)}, "
        f"{_pg_row_payloads(rows)}"
        ")"
    )
    row = conn.execute(text(sql)).one()
    return bytes(row[0])


@pytest.fixture(scope="module")
def gate_conn():
    _ensure_migrations()
    engine = create_engine(_sync_database_url())
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text(
                    "SELECT EXISTS ("
                    "  SELECT 1 FROM pg_proc p"
                    "  JOIN pg_namespace n ON n.oid = p.pronamespace"
                    "  WHERE n.nspname = 'gate' AND p.proname = '_canonical_record'"
                    ")"
                )
            ).scalar()
            if not exists:
                pytest.skip("gate._canonical_record not present (migration 039 not applied)")
            yield conn
    except OSError as exc:
        pytest.skip(f"Postgres unavailable: {exc}")
    finally:
        engine.dispose()


@pytest.mark.integration
def test_gate_record_parity_all_types(gate_conn) -> None:
    fields = {
        "amount": Decimal("12.34"),
        "ascii": "plain",
        "count": 42,
        "cyrillic": "Привет",
        "day": date(2026, 6, 27),
        "flag": True,
        "missing": None,
        "prefs": {"b": 2, "a": 1},
        "ratio": 0.1,
        "tags": ["z", "a"],
        "uid": UUID("00000000-0000-0000-0000-000000000001"),
        "when": datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc),
    }
    ordered_fields = ordered_entries_from_mapping(fields)
    py_bytes = canonical_serialize_ordered_record(
        table="users",
        operation="update",
        locator=[],
        fields=ordered_fields,
    )
    pg_bytes = _gate_record_bytes(
        gate_conn,
        table="users",
        operation="update",
        locator=[],
        fields=ordered_fields,
    )
    assert pg_bytes == py_bytes


@pytest.mark.integration
def test_gate_record_none_vs_empty_string(gate_conn) -> None:
    null_fields = [field_entry("note", None)]
    empty_fields = [field_entry("note", "")]
    null_py = canonical_serialize_ordered_record(
        table="users", operation="update", locator=[], fields=null_fields
    )
    empty_py = canonical_serialize_ordered_record(
        table="users", operation="update", locator=[], fields=empty_fields
    )
    assert _gate_record_bytes(
        gate_conn, table="users", operation="update", locator=[], fields=null_fields
    ) == null_py
    assert _gate_record_bytes(
        gate_conn, table="users", operation="update", locator=[], fields=empty_fields
    ) == empty_py
    assert null_py != empty_py


@pytest.mark.integration
@pytest.mark.parametrize(
    ("raw",),
    [
        (19.99,),
        ("19.99",),
        (1.2e-07,),
        ('{"a":1}',),
        ('["z","a"]',),
    ],
)
def test_gate_record_numeric_and_json_strings(gate_conn, raw: object) -> None:
    entries = [field_entry("v", raw)]
    py_bytes = canonical_serialize_ordered_record(
        table="users", operation="update", locator=[], fields=entries
    )
    assert (
        _gate_record_bytes(
            gate_conn, table="users", operation="update", locator=[], fields=entries
        )
        == py_bytes
    )


@pytest.mark.integration
def test_gate_record_multi_key_order_sensitive(gate_conn) -> None:
    first = [("a", False, "1"), ("b", False, "2")]
    second = [("b", False, "2"), ("a", False, "1")]
    py_first = canonical_serialize_ordered_record(
        table="users", operation="update", locator=[], fields=first
    )
    py_second = canonical_serialize_ordered_record(
        table="users", operation="update", locator=[], fields=second
    )
    assert (
        _gate_record_bytes(
            gate_conn, table="users", operation="update", locator=[], fields=first
        )
        == py_first
    )
    assert (
        _gate_record_bytes(
            gate_conn, table="users", operation="update", locator=[], fields=second
        )
        == py_second
    )
    assert py_first != py_second


@pytest.mark.integration
def test_gate_batch_two_row_order(gate_conn) -> None:
    rows = [
        ordered_entries_from_mapping(
            {"listing_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "status": "success"}
        ),
        ordered_entries_from_mapping(
            {"listing_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "status": "error"}
        ),
    ]
    py_bytes = canonical_serialize_ordered_batch(
        table="scrape_logs",
        operation="insert",
        locator=[],
        rows=rows,
    )
    assert (
        _gate_batch_bytes(
            gate_conn,
            table="scrape_logs",
            operation="insert",
            locator=[],
            rows=rows,
        )
        == py_bytes
    )


@pytest.mark.integration
def test_gate_hmac_hex_parity(gate_conn) -> None:
    """Requires Supabase vault extension; skipped on plain Postgres."""
    vault_ok = gate_conn.execute(
        text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM pg_extension e"
            "  JOIN pg_namespace n ON n.oid = e.extnamespace"
            "  WHERE e.extname = 'supabase_vault'"
            ")"
        )
    ).scalar()
    if not vault_ok:
        pytest.skip("supabase_vault extension not installed")

    secret = "parity-test-secret-039"
    fields = ordered_entries_from_mapping({"amount": Decimal("12.345"), "count": 42})
    canonical = canonical_serialize_ordered_record(
        table="users",
        operation="update",
        locator=[],
        fields=fields,
    )
    py_hex = hmac.new(secret.encode("utf-8"), canonical, digestmod="sha256").hexdigest()

    gate_conn.execute(
        text(
            "SELECT vault.create_secret(:secret, 'data_firewall_signing_secret', "
            "'039 parity test', true)"
        ),
        {"secret": secret},
    )
    pg_hex = gate_conn.execute(
        text(
            "SELECT gate._hmac_hex(gate._canonical_record("
            "'users', 'update', ARRAY[]::gate.field_entry[], "
            f"{_pg_field_entries(fields)}"
            "))"
        )
    ).scalar()
    assert pg_hex == py_hex
