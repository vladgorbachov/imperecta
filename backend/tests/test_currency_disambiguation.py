"""Ambiguous currency tokens resolve against the marketplace whitelist."""

from __future__ import annotations

from app.common.html_parsing import currency_token_is_ambiguous
from app.modules.ingestion.gate import disambiguate_currency

MD_WHITELIST = frozenset({"MDL", "EUR", "USD"})
RO_WHITELIST = frozenset({"RON", "EUR", "USD"})
SE_WHITELIST = frozenset({"SEK", "EUR", "USD"})


def test_moldovan_lei_resolves_to_mdl() -> None:
    assert disambiguate_currency("RON", "1800.00 Lei", MD_WHITELIST) == "MDL"


def test_cyrillic_lei_resolves_to_mdl() -> None:
    assert disambiguate_currency("RON", "1 800 лей", MD_WHITELIST) == "MDL"


def test_romanian_lei_stays_ron() -> None:
    assert disambiguate_currency("RON", "1800 lei", RO_WHITELIST) == "RON"


def test_nordic_kr_resolves_by_country() -> None:
    assert disambiguate_currency("SEK", "129 kr", SE_WHITELIST) == "SEK"
    assert (
        disambiguate_currency("SEK", "129 kr", frozenset({"NOK", "EUR", "USD"}))
        == "NOK"
    )


def test_explicit_iso_code_never_remapped() -> None:
    # raw text carries a real ISO code, not a shared token — keep the detection
    assert disambiguate_currency("RON", "1800 RON", MD_WHITELIST) == "RON"


def test_multiple_allowed_siblings_keep_detection() -> None:
    wl = frozenset({"NOK", "DKK", "EUR"})
    assert disambiguate_currency("SEK", "99 kr", wl) == "SEK"


def test_token_ambiguity_probe() -> None:
    assert currency_token_is_ambiguous("129 kr")
    assert currency_token_is_ambiguous("1800 Lei")
    assert not currency_token_is_ambiguous("1800 RON")
    assert not currency_token_is_ambiguous(None)
