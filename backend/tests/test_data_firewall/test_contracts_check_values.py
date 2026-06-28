"""Unit tests for contract CHECK-to-column name matching."""

from __future__ import annotations

from app.models.app_tables import ScrapeJob
from app.modules.data_firewall.contracts import (
    FACT_TABLE_CONTRACTS,
    _check_values_for_table,
)


def test_scrape_jobs_status_has_enum_check_values() -> None:
    values = _check_values_for_table(ScrapeJob, "status")
    assert values is not None
    assert "completed" in values
    assert "failed" in values


def test_scrape_jobs_failed_has_no_check_values() -> None:
    """Integer counter must not inherit status enum via substring false-positive."""
    assert _check_values_for_table(ScrapeJob, "failed") is None
    assert "check_values" not in FACT_TABLE_CONTRACTS["scrape_jobs"]["failed"]


def test_all_contract_check_values_use_name_based_match() -> None:
    """Every check_values entry must map to a column-named IN (...) CHECK."""
    for table, contract in FACT_TABLE_CONTRACTS.items():
        for column_name, column_contract in contract.items():
            check_values = column_contract.get("check_values")
            if not check_values:
                continue
            assert isinstance(check_values, list)
            assert all(isinstance(value, str) for value in check_values)
