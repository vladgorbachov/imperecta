"""Marketplace locale resolution: domain TLD → country → local currency.

Used to determine the "Local currency" semantics for a marketplace when the
display-currency switch is set to "local". The resolution prefers the domain
TLD over `dim_marketplace.country_code` because the TLD reflects the operating
country of the storefront, while `country_code` may carry a different
business meaning (e.g. company registration country).
"""

from __future__ import annotations

from typing import Protocol

TLD_TO_COUNTRY: dict[str, str] = {
    "md": "MD",
    "ro": "RO",
    "bg": "BG",
    "com.ua": "UA",
    "ua": "UA",
    "kz": "KZ",
    "ee": "EE",
    "lt": "LT",
    "lv": "LV",
    "pl": "PL",
    "hu": "HU",
    "cz": "CZ",
    "sk": "SK",
    "de": "DE",
    "fr": "FR",
    "it": "IT",
    "es": "ES",
    "uk": "GB",
    "co.uk": "GB",
}

GENERIC_TLDS: frozenset[str] = frozenset(
    {
        "com",
        "net",
        "org",
        "shop",
        "store",
        "biz",
        "info",
        "io",
        "app",
        "co",
        "me",
        "eu",
    }
)

COUNTRY_TO_CURRENCY: dict[str, str] = {
    "MD": "MDL",
    "RO": "RON",
    # Bulgaria adopted the euro on 2026-01-01; lev (BGN) is no longer legal tender.
    "BG": "EUR",
    "UA": "UAH",
    "KZ": "KZT",
    "EE": "EUR",
    "LT": "EUR",
    "LV": "EUR",
    "PL": "PLN",
    "HU": "HUF",
    "CZ": "CZK",
    "SK": "EUR",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "GB": "GBP",
}

LocalResolutionSource = str
SOURCE_TLD: LocalResolutionSource = "tld"
SOURCE_COUNTRY_CODE: LocalResolutionSource = "country_code"
SOURCE_PARSE_CURRENCY: LocalResolutionSource = "parse_currency"
SOURCE_UNKNOWN: LocalResolutionSource = "unknown"


_KNOWN_TLDS: tuple[str, ...] = tuple(
    sorted({*TLD_TO_COUNTRY.keys(), *GENERIC_TLDS}, key=len, reverse=True)
)


class _MarketplaceLike(Protocol):
    domain: str | None
    country_code: str | None


def _normalize_domain(domain: str | None) -> str:
    """Lowercase host without scheme/path, leading dots, or `www.` prefix."""
    if not domain:
        return ""
    value = domain.strip().lower()
    for prefix in ("https://", "http://"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    value = value.split("/", 1)[0]
    value = value.split(":", 1)[0]
    value = value.lstrip(".")
    if value.startswith("www."):
        value = value[len("www.") :]
    return value


def extract_tld(domain: str | None) -> str | None:
    """Return the longest known TLD suffix that matches ``domain``.

    Multi-segment ccTLDs (e.g. ``com.ua``) take precedence over their shorter
    parents (``ua``) because ``_KNOWN_TLDS`` is sorted by length descending.
    Returns ``None`` when no known TLD matches.
    """
    host = _normalize_domain(domain)
    if not host:
        return None
    for tld in _KNOWN_TLDS:
        if host == tld or host.endswith("." + tld):
            return tld
    return None


def resolve_local_currency_from_parts(
    domain: str | None,
    country_code: str | None,
) -> tuple[str | None, LocalResolutionSource]:
    """Pure helper that does not require a SQLAlchemy model instance.

    Resolution order:
    1. Domain TLD → country (from :data:`TLD_TO_COUNTRY`) → currency.
    2. Fallback to ``country_code`` → currency.
    3. ``(None, "unknown")`` when neither produces a known currency.
    """
    tld = extract_tld(domain)
    if tld and tld in TLD_TO_COUNTRY:
        country = TLD_TO_COUNTRY[tld]
        currency = COUNTRY_TO_CURRENCY.get(country)
        if currency:
            return currency, SOURCE_TLD

    iso_country = (country_code or "").strip().upper()
    if iso_country and iso_country in COUNTRY_TO_CURRENCY:
        return COUNTRY_TO_CURRENCY[iso_country], SOURCE_COUNTRY_CODE

    return None, SOURCE_UNKNOWN


def resolve_local_currency(
    marketplace: _MarketplaceLike,
) -> tuple[str | None, LocalResolutionSource]:
    """Determine the "Local currency" display semantics for a marketplace.

    Returns:
        ``(currency_code, source)`` where ``currency_code`` is an ISO 4217
        code or ``None`` when undeterminable, and ``source`` is one of
        ``"tld"``, ``"country_code"``, ``"parse_currency"``, ``"unknown"``.

    The ``"parse_currency"`` source is reserved for callers that fall back
    to the price's parsed currency when this function returns ``"unknown"``;
    this function itself only returns the first three sources.

    Resolution order:
    1. Parse ``marketplace.domain`` → extract TLD → look up
       :data:`TLD_TO_COUNTRY`. If matched → look up country in
       :data:`COUNTRY_TO_CURRENCY` → return ``(currency, "tld")``.
    2. If TLD lookup fails (generic TLD or unknown TLD) → fall back to
       ``marketplace.country_code`` → look up in :data:`COUNTRY_TO_CURRENCY`
       → return ``(currency, "country_code")``.
    3. If ``country_code`` is also empty/unknown → return
       ``(None, "unknown")``. The caller decides what to do (show the
       parsed currency or disable the local-currency UI).
    """
    return resolve_local_currency_from_parts(
        getattr(marketplace, "domain", None),
        getattr(marketplace, "country_code", None),
    )
