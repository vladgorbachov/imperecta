"""FX-MARKET-RESTRICT: nine-currency allowlist, JPY seed, pair derivation tests."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.modules.market_data.forex_pairs import (
    DEFAULT_FOREX_ALLOWED_CURRENCIES,
    FOREX_PRIMARY_PAIRS,
    PAIR_DIRECTION,
    derive_forex_pairs,
    expand_forex_favorites_with_inverses,
)
from app.modules.market_data.ingestion import IngestionService

MIGRATION_026 = Path(__file__).resolve().parents[1] / "alembic/versions/026_forex_nine_currency_allowlist.py"
FOREX_SOURCES = [
    Path(__file__).resolve().parents[1] / "app/modules/market_data/forex_pairs.py",
    Path(__file__).resolve().parents[1] / "app/modules/market_data/ingestion.py",
    Path(__file__).resolve().parents[1] / "app/modules/market_data/reader.py",
]


def _sample_currency_rows() -> list[dict]:
    """Per-currency rows with rate_to_eur (EUR identity implicit)."""
    return [
        {"currency_code": "USD", "rate_to_eur": 0.92},
        {"currency_code": "GBP", "rate_to_eur": 0.78},
        {"currency_code": "JPY", "rate_to_eur": 0.0062},
        {"currency_code": "CHF", "rate_to_eur": 1.05},
        {"currency_code": "MDL", "rate_to_eur": 0.051},
        {"currency_code": "RON", "rate_to_eur": 0.20},
        {"currency_code": "PLN", "rate_to_eur": 0.23},
        {"currency_code": "TRY", "rate_to_eur": 0.027},
    ]


@pytest.mark.asyncio
async def test_forex_ingest_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only allowlisted currencies are persisted; SEK and other extras are skipped."""
    monkeypatch.setattr(
        "app.modules.market_data.ingestion.Settings",
        lambda: SimpleNamespace(forex_allowed_currency_set=DEFAULT_FOREX_ALLOWED_CURRENCIES),
    )
    monkeypatch.setattr(
        "app.modules.market_data.fetching.fetch_forex_rates",
        AsyncMock(
            return_value=[
                {"pair": "EUR/USD", "rate": 1.08, "change_24h": None},
                {"pair": "EUR/GBP", "rate": 0.86, "change_24h": None},
                {"pair": "EUR/SEK", "rate": 11.5, "change_24h": None},
                {"pair": "EUR/JPY", "rate": 160.0, "change_24h": None},
            ]
        ),
    )
    monkeypatch.setattr(
        "app.modules.market_data.fetching.fetch_crypto_prices",
        AsyncMock(return_value=([], False)),
    )

    fake_db = SimpleNamespace(commit=AsyncMock())
    service = IngestionService(fake_db)
    persist_forex = AsyncMock(return_value=3)
    service.persist_forex = persist_forex
    service.persist_crypto = AsyncMock(return_value=0)

    await service.ingest_all(include_commodities=False)

    forex_items = persist_forex.await_args.args[0]
    currencies = {item.currency_code for item in forex_items}
    assert currencies == {"USD", "GBP", "JPY"}
    assert "SEK" not in currencies


def test_jpy_seeded() -> None:
    """Migration 026 inserts JPY into dim_currency."""
    text = MIGRATION_026.read_text(encoding="utf-8")
    assert "'JPY', 'Japanese Yen', '¥', 0, true" in text
    assert "is_active" in text
    assert "ON CONFLICT (currency_code) DO NOTHING" in text
    assert DEFAULT_FOREX_ALLOWED_CURRENCIES == frozenset(
        {"USD", "EUR", "GBP", "JPY", "CHF", "MDL", "RON", "PLN", "TRY"},
    )


def test_cleanup_removes_non9() -> None:
    """Migration 026 deletes non-allowlisted fact_currency_rate rows only."""
    text = MIGRATION_026.read_text(encoding="utf-8")
    assert "DELETE FROM fact_currency_rate WHERE currency_code NOT IN" in text
    assert "fact_crypto_price" not in text
    assert "fact_commodity_price" not in text
    for code in DEFAULT_FOREX_ALLOWED_CURRENCIES:
        assert f"'{code}'" in text


def test_pair_derivation_generic() -> None:
    """Derived pairs follow A/B = units of B per 1 A; inverse equals 1/rate."""
    rows = _sample_currency_rows()
    pairs = derive_forex_pairs(rows)
    by_symbol = {p["symbol"]: p["rate"] for p in pairs}

    assert PAIR_DIRECTION.startswith("units of quote per 1 base")

    eur_usd = by_symbol["EUR/USD"]
    assert eur_usd == pytest.approx(1.0 / 0.92, rel=1e-6)
    assert by_symbol["USD/EUR"] == pytest.approx(1.0 / eur_usd, rel=1e-6)

    usd_jpy = by_symbol["USD/JPY"]
    assert usd_jpy == pytest.approx(0.92 / 0.0062, rel=1e-6)
    assert by_symbol["JPY/USD"] == pytest.approx(1.0 / usd_jpy, rel=1e-6)

    for base, quote in FOREX_PRIMARY_PAIRS:
        assert f"{base}/{quote}" in by_symbol
        assert f"{quote}/{base}" in by_symbol


def test_absent_currency_pair_omitted() -> None:
    """Missing allowlisted currency omits dependent pairs without fabrication."""
    rows = [
        {"currency_code": "USD", "rate_to_eur": 0.92},
        {"currency_code": "GBP", "rate_to_eur": 0.78},
    ]
    pairs = derive_forex_pairs(rows)
    symbols = {p["symbol"] for p in pairs}
    assert "EUR/USD" in symbols
    assert "GBP/USD" in symbols
    assert "USD/JPY" not in symbols
    assert "JPY/USD" not in symbols
    assert "MDL/EUR" not in symbols


def test_expand_forex_favorites_with_inverses_adds_reciprocal() -> None:
    """EUR/USD selection expands to include USD/EUR for ticker filtering."""
    assert expand_forex_favorites_with_inverses(["EUR/USD"]) == {"EUR/USD", "USD/EUR"}


def test_expand_forex_favorites_with_inverses_empty() -> None:
    assert expand_forex_favorites_with_inverses([]) == set()


def test_expand_forex_favorites_with_inverses_malformed_no_slash() -> None:
    assert expand_forex_favorites_with_inverses(["BTC"]) == {"BTC"}


def test_no_hardcoded_rates() -> None:
    """Forex restrict code must not embed literal FX rate constants."""
    suspicious = (
        r"1\.08",
        r"110\.",
        r"0\.92",
        r"rate\s*=\s*1\.[0-9]{2}",
        r"hardcoded.*rate",
    )
    for path in FOREX_SOURCES:
        text = path.read_text(encoding="utf-8")
        for pattern in suspicious:
            import re

            assert re.search(pattern, text) is None, f"{path.name} matches {pattern}"


def test_forex_allowed_currencies_env_default() -> None:
    """Settings default matches the nine-currency allowlist."""
    default = Settings.model_fields["forex_allowed_currencies"].default
    assert default == "USD,EUR,GBP,JPY,CHF,MDL,RON,PLN,TRY"
    parsed = frozenset(part.strip().upper() for part in default.split(",") if part.strip())
    assert parsed == DEFAULT_FOREX_ALLOWED_CURRENCIES
