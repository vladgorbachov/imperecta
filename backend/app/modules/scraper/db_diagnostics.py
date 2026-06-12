"""Shared DB diagnostic queries for admin tooling and debug scripts."""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger(__name__)


def _jsonable(value: Any) -> Any:
    """Convert DB row values to JSON-serializable primitives."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _rows_from_execute(
    conn: Connection,
    sql: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Execute SQL and return list of dicts with JSON-friendly values."""
    result = conn.execute(text(sql), params or {})
    keys = result.keys()
    out: list[dict[str, Any]] = []
    for row in result:
        d: dict[str, Any] = {}
        for i, k in enumerate(keys):
            d[str(k)] = _jsonable(row[i])
        out.append(d)
    return out


def _scalar_int(conn: Connection, sql: str) -> int | None:
    row = conn.execute(text(sql)).scalar_one_or_none()
    if row is None:
        return None
    return int(row)


def _list_dim_fact_tables(conn: Connection) -> list[str]:
    q = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND (table_name LIKE 'dim_%' OR table_name LIKE 'fact_%')
        ORDER BY table_name
        """
    )
    rows = conn.execute(q).all()
    return [str(r[0]) for r in rows]


def collect_db_diagnostics(engine: Engine) -> dict[str, Any]:
    """
    Run diagnostic SQL against the configured database.

    Returns a dict suitable for JSON responses and markdown reports.
    """
    payload: dict[str, Any] = {
        "alembic_version": None,
        "counts": {},
        "listings_recent": [],
        "scrape_logs_recent": [],
        "table_row_counts": {},
        "errors": [],
    }

    try:
        with engine.connect() as conn:
            try:
                ver = conn.execute(
                    text("SELECT version_num FROM alembic_meta.alembic_version LIMIT 1"),
                ).scalar_one_or_none()
                payload["alembic_version"] = str(ver) if ver is not None else None
            except Exception as exc:
                payload["errors"].append(f"alembic_version: {exc}")
                logger.warning("db_diagnostics alembic_version failed: %s", exc)

            count_queries = {
                "dim_marketplace_active": (
                    "SELECT COUNT(*) FROM dim_marketplace WHERE is_active = true"
                ),
                "fact_listing": "SELECT COUNT(*) FROM fact_listing",
                "fact_price": "SELECT COUNT(*) FROM fact_price",
                "scrape_logs": "SELECT COUNT(*) FROM scrape_logs",
            }
            for key, sql in count_queries.items():
                try:
                    payload["counts"][key] = _scalar_int(conn, sql)
                except Exception as exc:
                    payload["errors"].append(f"count {key}: {exc}")
                    payload["counts"][key] = None

            listings_sql = """
            SELECT
              fl.id, fl.external_url, fl.last_checked_at, fl.last_error,
              fl.consecutive_errors, fl.failure_streak, fl.last_price, dm.name AS marketplace,
              dp.name AS product_name
            FROM fact_listing fl
            JOIN dim_marketplace dm ON fl.marketplace_id = dm.id
            LEFT JOIN dim_product dp ON fl.product_id = dp.id
            ORDER BY fl.last_checked_at DESC NULLS LAST
            LIMIT 20
            """
            try:
                payload["listings_recent"] = _rows_from_execute(conn, listings_sql)
            except Exception as exc:
                payload["errors"].append(f"listings_recent: {exc}")

            try:
                payload["scrape_logs_recent"] = _rows_from_execute(
                    conn,
                    "SELECT * FROM scrape_logs ORDER BY created_at DESC LIMIT 30",
                )
            except Exception as exc:
                payload["errors"].append(f"scrape_logs_recent: {exc}")

            for tbl in _list_dim_fact_tables(conn):
                try:
                    n = _scalar_int(conn, f'SELECT COUNT(*) FROM "{tbl}"')
                    payload["table_row_counts"][tbl] = n
                except Exception as exc:
                    payload["errors"].append(f"count {tbl}: {exc}")
                    payload["table_row_counts"][tbl] = None

    except Exception as exc:
        payload["errors"].append(f"connection: {exc}")
        logger.exception("db_diagnostics failed")

    return payload
