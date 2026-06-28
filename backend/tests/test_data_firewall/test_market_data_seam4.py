"""DB-free tests for market-data seam 4 (#33 dim_date gate routing + trim migration)."""

from __future__ import annotations

import inspect
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.sql.dml import Insert

from app.modules.data_firewall.contracts import FACT_TABLE_CONTRACTS, TABLE_LOCATORS
from app.modules.data_firewall.firewall import evaluate_market
from app.modules.data_firewall.signing import reset_signing_settings_cache
from app.modules.market_data import ingestion as market_ingestion
from app.modules.market_data.ingestion import _ensure_dim_date
from app.modules.persist.scrape_gate_fields import (
    build_dim_date_fields_from_day,
)
from app.modules.persist.writer import (
    PersistContext,
    SUPPORTED_WRITE_OPERATIONS,
    write_sync,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DIM_DATE_COLUMNS = (
    "date_id",
    "full_date",
    "year",
    "quarter",
    "month",
    "month_name",
    "week_iso",
    "day_of_month",
    "day_of_week",
    "day_name",
    "is_weekend",
    "is_last_day_of_month",
)


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def test_dim_date_already_registered_in_all_four_maps() -> None:
    assert "dim_date" in FACT_TABLE_CONTRACTS
    assert TABLE_LOCATORS["dim_date"] == ("date_id",)
    assert SUPPORTED_WRITE_OPERATIONS["dim_date"] == frozenset({"insert"})


def test_migration_trim_single_statement_and_fixed_boundary() -> None:
    source = (BACKEND_ROOT / "alembic/versions/037_trim_dim_date_preseed.py").read_text(
        encoding="utf-8",
    )
    assert 'op.execute("DELETE FROM dim_date WHERE date_id > 20260627")' in source
    assert "CURRENT_DATE" not in source
    assert "FK-safe" in source or "FK sources" in source


def test_migration_downgrade_is_no_op_with_comment() -> None:
    source = (BACKEND_ROOT / "alembic/versions/037_trim_dim_date_preseed.py").read_text(
        encoding="utf-8",
    )
    downgrade = source.split("def downgrade()", 1)[1]
    assert "op.execute" not in downgrade
    assert "Not reversible" in downgrade or "not reversible" in downgrade.lower()


def test_build_dim_date_fields_from_day_all_not_null_columns() -> None:
    d = date(2026, 6, 28)
    fields = build_dim_date_fields_from_day(d)

    for col in REQUIRED_DIM_DATE_COLUMNS:
        assert col in fields, col

    assert fields["date_id"] == 20260628
    assert fields["full_date"] == d
    assert fields["year"] == 2026
    assert fields["month"] == 6
    assert fields["quarter"] == 2
    assert fields["day_of_month"] == 28
    assert fields["is_weekend"] is True
    assert fields["is_last_day_of_month"] is False
    assert "fiscal_year" not in fields
    assert "fiscal_quarter" not in fields


def test_no_raw_db_add_dim_date_in_market_data_ingestion() -> None:
    source = inspect.getsource(market_ingestion)
    assert "db.add(row)" not in source
    assert "db.add(DimDate" not in source
    assert "build_dim_date_fields_from_day" in source


def test_dim_date_insert_uses_on_conflict_do_nothing() -> None:
    fields = build_dim_date_fields_from_day(date(2026, 6, 28))
    outcome = evaluate_market(
        fields,
        table="dim_date",
        operation="insert",
        db=MagicMock(),
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None

    captured: list = []

    def _execute(stmt):
        captured.append(stmt)
        result = MagicMock()
        result.rowcount = 1
        return result

    db = MagicMock()
    db.execute.side_effect = _execute
    write_sync(
        db,
        outcome.signed_record,
        ctx=PersistContext(source="test", date_id=fields["date_id"]),
    )
    assert len(captured) == 1
    assert isinstance(captured[0], Insert)
    assert captured[0]._post_values_clause is not None  # noqa: SLF001


@patch("app.modules.market_data.ingestion.write_sync")
@patch("app.modules.market_data.ingestion.evaluate_market")
def test_ensure_dim_date_routes_through_gate(
    mock_eval: MagicMock,
    mock_write: MagicMock,
) -> None:
    d = date(2026, 6, 28)
    fields = build_dim_date_fields_from_day(d)
    signed = MagicMock()
    mock_eval.return_value = MagicMock(passed=True, signed_record=signed)
    mock_write.return_value = MagicMock(ok=True, rows_affected=1)

    db = MagicMock()
    db.scalar = MagicMock(side_effect=[None, 20260628])
    db.execute.return_value.scalar_one_or_none.return_value = 20260628
    db.flush = MagicMock()

    date_id = _ensure_dim_date(db, d)

    assert date_id == 20260628
    mock_eval.assert_called_once()
    assert mock_eval.call_args.kwargs["table"] == "dim_date"
    assert mock_eval.call_args.kwargs["operation"] == "insert"
    assert mock_eval.call_args.args[0] == fields
    mock_write.assert_called_once()
    db.add.assert_not_called()


@patch("app.modules.market_data.ingestion.write_sync")
@patch("app.modules.market_data.ingestion.evaluate_market")
def test_ensure_dim_date_skips_gate_when_row_exists(
    mock_eval: MagicMock,
    mock_write: MagicMock,
) -> None:
    d = date(2026, 6, 27)
    db = MagicMock()
    db.scalar = MagicMock(return_value=20260627)

    date_id = _ensure_dim_date(db, d)

    assert date_id == 20260627
    mock_eval.assert_not_called()
    mock_write.assert_not_called()
    db.add.assert_not_called()
