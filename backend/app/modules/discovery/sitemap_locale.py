"""Which sub-sitemaps of a multi-locale shop to walk.

pigu.lt (2026-09-19) ships one sitemap tree per storefront language —
406 `lt/sitemap-products-N.xml`, 406 `ru/sitemap-products-N.xml`, plus an
image twin of each — and the pool already holds 1.05M `/lt/...` listings.
Walking the `ru/` files would have added every offer a second time under
another URL; walking the image files re-reads locs the product files list.

The primitives live in rust_core (sitemap.rs); the Python twins below are
the reference implementation the parity tests pin, used when the engine
flag is off. `canonical_locale_sync` is the DB side: the locale prefix the
shop's own pool is written under.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.common import html_parsing as _hp

_LOCALE_SEGMENT_RE = re.compile(r"^[a-z]{2}(?:[-_][a-z]{2})?$")
# Sub-sitemaps whose name says they carry no live offers: media extension
# files (locs restated), discontinued catalogs (tsbohemia: 2150 of 2759
# files are `sitemap-products-disabled-N-cs.xml`), user content.
_NOISE_SITEMAP_TOKENS = frozenset({
    "image", "images", "img", "video", "videos",
    "disabled", "discontinued", "archive", "archived", "expired", "inactive", "unavailable",
    "review", "reviews", "consultation", "consultations", "question", "questions",
    "comment", "comments", "discussion", "discussions", "rating", "ratings",
})
_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")

# Share of a pool sample that must sit under one locale prefix before it is
# taken as the shop's canonical locale (below that, nothing is filtered).
CANONICAL_LOCALE_MIN_SHARE = 0.8
CANONICAL_LOCALE_SAMPLE = 2000

# Country -> storefront language used only when the pool is still empty and
# the sitemap index offers several locales. Deliberately short: only
# countries with one unambiguous national language.
COUNTRY_LANGUAGE: dict[str, str] = {
    "LT": "lt",
    "LV": "lv",
    "EE": "et",
    "PL": "pl",
    "CZ": "cs",
    "SK": "sk",
    "HU": "hu",
    "RO": "ro",
    "BG": "bg",
    "UA": "uk",
    "DE": "de",
    "AT": "de",
    "FR": "fr",
    "IT": "it",
    "ES": "es",
    "PT": "pt",
    "NL": "nl",
    "GR": "el",
    "HR": "hr",
    "SI": "sl",
    "RS": "sr",
    "SE": "sv",
    "FI": "fi",
    "DK": "da",
    "NO": "no",
}


@dataclass(frozen=True)
class SubfileSelection:
    kept: list[str] = field(default_factory=list)
    skipped_noise: int = 0
    skipped_locale: int = 0
    locale: str | None = None


def url_locale_segment(url: str) -> str | None:
    """First path segment when it reads as a locale code ("lt", "en-us")."""
    if _hp._use_rust():
        return _hp._rust_core.url_locale_segment(url)
    first = urlparse(url).path.lstrip("/").split("/", 1)[0].lower()
    return first if _LOCALE_SEGMENT_RE.match(first) else None


def is_noise_sitemap(url: str) -> bool:
    """Media / discontinued / user-content sub-sitemaps — never walked."""
    if _hp._use_rust():
        return _hp._rust_core.is_noise_sitemap(url)
    name = urlparse(url).path.rsplit("/", 1)[-1].lower()
    return any(token in _NOISE_SITEMAP_TOKENS for token in _TOKEN_SPLIT_RE.split(name))


def select_sitemap_subfiles(
    urls: list[str],
    canonical: str | None = None,
    country_hint: str | None = None,
    whole_tree: bool = False,
) -> SubfileSelection:
    """Drop noise files; keep one storefront locale's files.

    `whole_tree` (the caller sees the shop's full index): on a tree with 2+
    locales the winner is `canonical` when the index has it (the pool's URL
    prefix — a tie-breaker only: tsbohemia's files sit under /cs/ while its
    pool is /en/ through hreflang alternates), else the country's language,
    else the first locale in index order; a single-locale index is never
    touched. A shard (3 files in isolation): `canonical` is the locale the
    coordinator elected on the whole index and is authoritative — a shard
    entirely under another locale is skipped whole — and without one
    nothing is dropped, so a shard never elects a locale from its own files.
    """
    if _hp._use_rust():
        raw = _hp._rust_core.select_sitemap_subfiles(urls, canonical, country_hint, whole_tree)
        return SubfileSelection(
            kept=list(raw["kept"]),
            skipped_noise=int(raw["skipped_noise"]),
            skipped_locale=int(raw["skipped_locale"]),
            locale=raw["locale"],
        )
    candidates: list[tuple[str, str | None]] = []
    locales: list[str] = []
    skipped_noise = 0
    for url in urls:
        if is_noise_sitemap(url):
            skipped_noise += 1
            continue
        locale = url_locale_segment(url)
        if locale is not None and locale not in locales:
            locales.append(locale)
        candidates.append((url, locale))
    canonical_l = (canonical or "").lower() or None
    chosen: str | None = None
    if whole_tree:
        if len(locales) >= 2:
            hint_l = (country_hint or "").lower() or None
            if canonical_l in locales:
                chosen = canonical_l
            elif hint_l in locales:
                chosen = hint_l
            else:
                chosen = locales[0]
    elif canonical_l is not None and any(l != canonical_l for l in locales):
        chosen = canonical_l
    kept: list[str] = []
    skipped_locale = 0
    for url, locale in candidates:
        if chosen is not None and locale is not None and locale != chosen:
            skipped_locale += 1
        else:
            kept.append(url)
    return SubfileSelection(
        kept=kept, skipped_noise=skipped_noise, skipped_locale=skipped_locale, locale=chosen
    )


def dominant_locale(urls: list[str], min_share: float = CANONICAL_LOCALE_MIN_SHARE) -> str | None:
    """The locale prefix at least `min_share` of `urls` share, else None."""
    if _hp._use_rust():
        return _hp._rust_core.dominant_locale(urls, min_share)
    if not urls:
        return None
    counts: dict[str, int] = {}
    for url in urls:
        locale = url_locale_segment(url)
        if locale is not None:
            counts[locale] = counts.get(locale, 0) + 1
    if not counts:
        return None
    locale, n = max(counts.items(), key=lambda item: item[1])
    return locale if n >= min_share * len(urls) else None


def country_language_hint(country_code: str | None) -> str | None:
    return COUNTRY_LANGUAGE.get((country_code or "").upper()) or None


def canonical_locale_sync(marketplace_id) -> str | None:
    """The locale prefix the shop's own pool is written under (sampled),
    None when the pool is empty or not locale-prefixed. A whole-tree
    tie-breaker only — pool URLs may sit in another locale than the
    sitemap files (hreflang selection at ingest)."""
    from sqlalchemy import select

    from app.database import sync_session_factory
    from app.models.facts import FactListing

    db = sync_session_factory()
    try:
        rows = db.execute(
            select(FactListing.external_url)
            .where(
                FactListing.marketplace_id == marketplace_id,
                FactListing.is_active,
            )
            .limit(CANONICAL_LOCALE_SAMPLE)
        ).all()
    finally:
        db.close()
    return dominant_locale([row[0] for row in rows if row[0]])


__all__ = [
    "CANONICAL_LOCALE_MIN_SHARE",
    "COUNTRY_LANGUAGE",
    "SubfileSelection",
    "canonical_locale_sync",
    "country_language_hint",
    "dominant_locale",
    "is_noise_sitemap",
    "select_sitemap_subfiles",
    "url_locale_segment",
]
