"""Transport A: persist → gate.exec_write / exec_write_batch (bound scalar params)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.modules.data_firewall.signing import SignedBatch, SignedRecord
from app.modules.data_firewall.signing_ordered import ordered_entries_from_mapping


class GateRpcError(Exception):
    """Mapped gate RPC failure (PG exception text → kind)."""

    def __init__(self, kind: str, message: str) -> None:
        self.kind = kind
        self.message = message
        super().__init__(message)


def _pg_error_message(exc: DBAPIError) -> str:
    orig = exc.orig
    if orig is not None:
        return str(orig)
    return str(exc)


def _classify_gate_error(message: str) -> str:
    if "invalid_signature" in message:
        return "invalid_signature"
    if "signing_unavailable" in message:
        return "signing_unavailable"
    return "rpc_error"


def _raise_gate_rpc_error(exc: DBAPIError) -> None:
    message = _pg_error_message(exc)
    kind = _classify_gate_error(message)
    raise GateRpcError(kind, message) from exc


def _field_entries_sql(
    entries: list[tuple[str, bool, str]],
    params: dict[str, Any],
    prefix: str,
) -> str:
    if not entries:
        return "ARRAY[]::gate.field_entry[]"
    parts: list[str] = []
    for idx, (key, is_null, val) in enumerate(entries):
        pk = f"{prefix}_k{idx}"
        pn = f"{prefix}_n{idx}"
        pv = f"{prefix}_v{idx}"
        params[pk] = key
        params[pn] = is_null
        params[pv] = val
        parts.append(f"ROW(:{pk}, :{pn}, :{pv})::gate.field_entry")
    return "ARRAY[" + ", ".join(parts) + "]::gate.field_entry[]"


def _row_payloads_sql(
    rows: list[list[tuple[str, bool, str]]],
    params: dict[str, Any],
) -> str:
    if not rows:
        return "ARRAY[]::gate.row_payload[]"
    parts: list[str] = []
    for row_idx, row in enumerate(rows):
        inner = _field_entries_sql(row, params, f"br{row_idx}")
        parts.append(f"ROW({inner})::gate.row_payload")
    return "ARRAY[" + ", ".join(parts) + "]::gate.row_payload[]"


def exec_write_record(db: Session, signed: SignedRecord) -> int:
    """Call gate.exec_write with ordered wire entries and return rows_affected."""
    locator_entries = ordered_entries_from_mapping(signed.locator)
    fields_entries = ordered_entries_from_mapping(signed.fields)
    params: dict[str, Any] = {
        "table": signed.table,
        "op": signed.operation,
        "sig": signed.signature,
    }
    locator_sql = _field_entries_sql(locator_entries, params, "lk")
    fields_sql = _field_entries_sql(fields_entries, params, "fk")
    sql = text(
        f"SELECT gate.exec_write(:table, :op, {locator_sql}, {fields_sql}, :sig)",
    )
    try:
        rowcount = db.execute(sql, params).scalar_one()
    except DBAPIError as exc:
        _raise_gate_rpc_error(exc)
    return int(rowcount)


def exec_write_batch(db: Session, signed: SignedBatch) -> int:
    """Call gate.exec_write_batch with ordered row payloads and return rows_affected."""
    locator_entries = ordered_entries_from_mapping(signed.locator)
    row_entries = [ordered_entries_from_mapping(row) for row in signed.rows]
    params: dict[str, Any] = {
        "table": signed.table,
        "op": signed.operation,
        "sig": signed.signature,
    }
    locator_sql = _field_entries_sql(locator_entries, params, "lk")
    rows_sql = _row_payloads_sql(row_entries, params)
    sql = text(
        f"SELECT gate.exec_write_batch(:table, :op, {locator_sql}, {rows_sql}, :sig)",
    )
    try:
        rowcount = db.execute(sql, params).scalar_one()
    except DBAPIError as exc:
        _raise_gate_rpc_error(exc)
    return int(rowcount)
