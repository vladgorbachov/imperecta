"""Pure-logic tests for scrape-day price_eur resolver (seam A)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.modules.currency.price_eur_resolver import resolve_price_eur
from app.modules.data_firewall.signing import reset_signing_settings_cache
from app.modules.data_firewall.update_validator import (
    SCRAPE_UPDATE_ALLOWLIST,
    authorize_scrape_update,
)
from app.modules.persist.scrape_gate_fields import build_listing_update_fields
from app.modules.persist.writer import build_fact_price_fields


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def test_resolve_price_eur_eur_base_quantized() -> None:
    db = MagicMock()
    result = resolve_price_eur(
        price=19.999,
        currency_code="eur",
        date_id=20250617,
        db=db,
    )
    assert result == Decimal("20.00")
    db.execute.assert_not_called()


def test_resolve_price_eur_non_eur_uses_scrape_day_date_id() -> None:
    db = MagicMock()
    captured: list = []

    def _execute(stmt):
        captured.append(stmt)
        row = MagicMock()
        row.rate_to_eur = Decimal("0.92")
        row.source = "ecb"
        result = MagicMock()
        result.all.return_value = [row]
        return result

    db.execute.side_effect = _execute

    result = resolve_price_eur(
        price=100,
        currency_code="USD",
        date_id=20250617,
        db=db,
    )

    assert result == Decimal("92.00")
    assert len(captured) == 1
    stmt = captured[0]
    where_sql = str(stmt.whereclause)
    assert "date_id" in where_sql
    assert "currency_code" in where_sql


def test_resolve_price_eur_missing_rate_returns_none() -> None:
    db = MagicMock()
    result_mock = MagicMock()
    result_mock.all.return_value = []
    db.execute.return_value = result_mock

    result = resolve_price_eur(
        price=50,
        currency_code="USD",
        date_id=20250617,
        db=db,
    )
    assert result is None


def test_resolve_price_eur_picks_deterministic_source() -> None:
    db = MagicMock()

    ecb = MagicMock(rate_to_eur=Decimal("0.90"), source="ecb")
    custom = MagicMock(rate_to_eur=Decimal("0.95"), source="custom")
    result_mock = MagicMock()
    result_mock.all.return_value = [custom, ecb]
    db.execute.return_value = result_mock

    result = resolve_price_eur(
        price=10,
        currency_code="USD",
        date_id=20250617,
        db=db,
    )
    assert result == Decimal("9.00")


def test_build_fact_price_fields_includes_price_eur() -> None:
    fields = build_fact_price_fields(
        listing_id=uuid4(),
        date_id=20250617,
        price=10.0,
        currency_code="USD",
        original_price=None,
        discount_pct=None,
        price_change_pct=None,
        scraped_at=datetime.now(tz=timezone.utc),
        scrape_job_id=None,
        price_eur=9.2,
    )
    assert fields["price_eur"] == 9.2

    eur_fields = build_fact_price_fields(
        listing_id=uuid4(),
        date_id=20250617,
        price=12.5,
        currency_code="EUR",
        original_price=None,
        discount_pct=None,
        price_change_pct=None,
        scraped_at=datetime.now(tz=timezone.utc),
        scrape_job_id=None,
        price_eur=12.5,
    )
    assert eur_fields["price_eur"] == 12.5


def test_denorm_allowlist_accepts_last_price_eur() -> None:
    fields = build_listing_update_fields(
        url_hash="hash",
        last_price=10.0,
        last_currency_code="USD",
        last_price_changed_at=datetime.now(tz=timezone.utc),
        last_price_eur=9.2,
    )
    outcome = authorize_scrape_update(
        table="fact_listing",
        kind="listing_denorm_success",
        fields=fields,
        db=MagicMock(),
    )
    assert outcome.passed is True

    no_change_fields = build_listing_update_fields(
        url_hash="hash",
        last_checked_at=datetime.now(tz=timezone.utc),
        last_price=10.0,
        last_currency_code="USD",
        last_price_eur=None,
    )
    no_change_outcome = authorize_scrape_update(
        table="fact_listing",
        kind="listing_denorm_no_change",
        fields=no_change_fields,
        db=MagicMock(),
    )
    assert no_change_outcome.passed is True


def test_denorm_no_change_allowlist_includes_last_price_eur() -> None:
    no_change_fields = build_listing_update_fields(
        url_hash="hash",
        last_checked_at=datetime.now(tz=timezone.utc),
        last_price=10.0,
        last_currency_code="EUR",
        last_price_eur=Decimal("9.20"),
    )
    allowed = SCRAPE_UPDATE_ALLOWLIST["fact_listing"]["listing_denorm_no_change"]
    assert set(no_change_fields.keys()) - {"url_hash"} <= allowed


def test_currency_module_has_no_scraper_ingestion_imports() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "app" / "modules" / "currency"
    forbidden = {"scraper", "ingestion"}
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top in forbidden or "scraper" in node.module or "ingestion" in node.module:
                    pytest.fail(f"forbidden import in {path}: {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in forbidden:
                        pytest.fail(f"forbidden import in {path}: {alias.name}")
