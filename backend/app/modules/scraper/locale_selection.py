"""Deterministic locale URL selection and Accept-Language for scraper fetches."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# English-first preference for locale selection (not a URL path hardcode).
ENGLISH_HREFLANG_PREFIX = "en"


def _normalize_hreflang(tag: str) -> str:
    return (tag or "").strip().lower()


def _is_english_hreflang(hreflang: str) -> bool:
    normalized = _normalize_hreflang(hreflang)
    return normalized == ENGLISH_HREFLANG_PREFIX or normalized.startswith(f"{ENGLISH_HREFLANG_PREFIX}-")


def select_locale_url(
    raw_url: str,
    alternates: dict[str, str] | None,
    marketplace_locale: str | None,
) -> str:
    """Pick one URL from hreflang alternates using a deterministic chain.

    Selection chain (first match wins):
    1. ENGLISH — alternate whose hreflang is ``en`` or ``en-*``.
    2. LOCAL — alternate whose hreflang matches ``marketplace_locale`` (exact or
       language subtag, e.g. ``fi`` matches ``fi-FI``).
    3. ANY — ``x-default`` alternate, else the first alternate value, else
       ``raw_url`` unchanged.

    ``marketplace_locale`` comes from ``DimMarketplace.locale`` (per-shop config).
    English preference is structural (hreflang tags), not a hardcoded URL path.
    """
    if not alternates:
        return raw_url

    for hreflang, url in alternates.items():
        if _is_english_hreflang(hreflang) and url:
            return url

    if marketplace_locale:
        mp_locale = _normalize_hreflang(marketplace_locale)
        mp_lang = mp_locale.split("-", 1)[0]
        for hreflang, url in alternates.items():
            if not url:
                continue
            normalized = _normalize_hreflang(hreflang)
            if normalized == mp_locale or normalized.split("-", 1)[0] == mp_lang:
                return url

    x_default = alternates.get("x-default")
    if x_default:
        return x_default

    for url in alternates.values():
        if url:
            return url

    return raw_url


def extract_canonical_url(soup: BeautifulSoup, page_url: str) -> str | None:
    """Return absolute canonical URL from ``<link rel=\"canonical\">`` when present."""
    link = soup.find("link", rel=lambda value: value and "canonical" in value)
    if not link:
        return None
    href = (link.get("href") or "").strip()
    if not href:
        return None
    canonical = urljoin(page_url, href)
    parsed = urlparse(canonical)
    if parsed.scheme not in {"http", "https"}:
        return None
    return parsed._replace(fragment="", query="").geturl()


def build_accept_language_header(marketplace_locale: str | None = None) -> str:
    """Build Accept-Language with English-first preference.

    English variants are always listed first. When ``marketplace_locale`` is set
    and is not English, it is included as a secondary preference so shops can
    serve the configured local language when English content is unavailable.
    """
    if marketplace_locale and not _is_english_hreflang(marketplace_locale):
        locale = _normalize_hreflang(marketplace_locale)
        return f"en, en-US;q=0.9, {locale};q=0.8"
    return "en, en-US;q=0.9"


__all__ = [
    "ENGLISH_HREFLANG_PREFIX",
    "build_accept_language_header",
    "extract_canonical_url",
    "select_locale_url",
]
