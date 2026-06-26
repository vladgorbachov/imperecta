"""Tests for migration 026 JPY seed."""

from __future__ import annotations

from pathlib import Path

MIGRATION_026 = Path(__file__).resolve().parents[1] / "alembic/versions/026_forex_nine_currency_allowlist.py"


def test_migration_026_jpy_inserts() -> None:
    """Migration 026 JPY INSERT must cover every NOT NULL dim_currency column."""
    text = MIGRATION_026.read_text(encoding="utf-8")
    assert "INSERT INTO dim_currency" in text
    assert "'JPY', 'Japanese Yen', '¥', 0, true" in text
    assert "is_active" in text
    assert "ON CONFLICT (currency_code) DO NOTHING" in text
    assert "DELETE FROM fact_currency_rate WHERE currency_code NOT IN" in text
