"""Pure post-fetch normalization: snippet cleanup, junk drop, relevance, dedup."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.modules.news.providers.base import SNIPPET_MAX_LENGTH, truncate_snippet
from app.modules.news.schemas import NewsItem

# Extensible junk patterns — feed self-descriptions and non-article stubs.
JUNK_TITLE_EXACT: frozenset[str] = frozenset(
    {
        "company announcements",
    },
)

JUNK_SOURCES: frozenset[str] = frozenset(
    {
        "feedloaderapi",
        "nbuffie",
        "unknown",
    },
)

JUNK_SNIPPET_PREFIXES: tuple[str, ...] = (
    "the latest company information, including net asset values",
)

_READ_MORE_SENTENCE = re.compile(r"^read more at\s+.+?\.?$", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_NON_ALNUM = re.compile(r"[^\w\s]", re.UNICODE)
_MULTI_SPACE = re.compile(r"\s+")

_RETAIL_TERM_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bretail\b",
        r"\be-?commerce\b",
        r"\bmarketplace\b",
        r"\bonline\s+store\b",
        r"\bconsumer\s+goods\b",
        r"\bshopper\b",
        r"\bbasket\b",
        r"\bcheckout\b",
        r"\bprices?\b",
        r"\bdiscount\b",
        r"\bsales?\b",
    )
)


def _collapse_whitespace(text: str) -> str:
    return _MULTI_SPACE.sub(" ", str(text or "").strip())


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [part.strip() for part in parts if part.strip()]


def _is_read_more_sentence(sentence: str) -> bool:
    return bool(_READ_MORE_SENTENCE.match(sentence.strip()))


def _strip_duplicate_trailing_sentences(sentences: list[str]) -> list[str]:
    if not sentences:
        return sentences
    trimmed = list(sentences)
    while len(trimmed) >= 2:
        last = trimmed[-1].strip().lower()
        previous = trimmed[-2].strip().lower()
        if last == previous:
            trimmed.pop()
            continue
        if _is_read_more_sentence(trimmed[-1]) and _is_read_more_sentence(trimmed[-2]):
            trimmed.pop()
            continue
        break
    return trimmed


def clean_snippet(text: str) -> str:
    """Collapse whitespace, drop duplicated tail sentences, cap length (idempotent)."""
    collapsed = _collapse_whitespace(text)
    if not collapsed:
        return ""

    sentences = _split_sentences(collapsed)
    if not sentences:
        sentences = [collapsed]

    deduped = _strip_duplicate_trailing_sentences(sentences)
    joined = " ".join(deduped).strip()
    return truncate_snippet(joined, max_length=SNIPPET_MAX_LENGTH)


def _normalize_text(value: str) -> str:
    lowered = _collapse_whitespace(value).lower()
    stripped = _NON_ALNUM.sub("", lowered)
    return _collapse_whitespace(stripped)


def _normalize_source(source: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(source or "").lower())


def _looks_like_feed_stub(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    for prefix in JUNK_SNIPPET_PREFIXES:
        if normalized.startswith(_normalize_text(prefix)):
            return True
    return False


def is_junk(item: NewsItem) -> bool:
    """True when the item is a feed self-description / non-article stub."""
    title_norm = _collapse_whitespace(item.title).lower()
    snippet_norm = _collapse_whitespace(item.snippet).lower()
    source_norm = _normalize_source(item.source)

    if title_norm in JUNK_TITLE_EXACT:
        return True
    if source_norm in JUNK_SOURCES:
        return True
    for prefix in JUNK_SNIPPET_PREFIXES:
        if snippet_norm.startswith(prefix) or snippet_norm == prefix:
            return True
    if title_norm == snippet_norm and _looks_like_feed_stub(title_norm):
        return True
    if _looks_like_feed_stub(title_norm) and _looks_like_feed_stub(snippet_norm):
        return True
    return False


def is_retail_relevant(item: NewsItem) -> bool:
    """True when title or snippet contains at least one retail/ecommerce lexicon term."""
    haystack = f"{item.title} {item.snippet}"
    return any(pattern.search(haystack) for pattern in _RETAIL_TERM_PATTERNS)


def _normalize_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw.lower())
    host = parsed.netloc
    path = parsed.path.rstrip("/")
    if not host and path:
        # Scheme-less URLs may land in path.
        return path.rstrip("/")
    return f"{host}{path}" if path else host


def _normalize_title(title: str) -> str:
    lowered = _collapse_whitespace(title).lower()
    no_punct = _NON_ALNUM.sub(" ", lowered)
    return _collapse_whitespace(no_punct)


def dedup_key(item: NewsItem) -> tuple[str, str]:
    """Normalized URL and title keys for deduplication."""
    return _normalize_url(item.url), _normalize_title(item.title)


@dataclass(frozen=True)
class NormalizeCounts:
    """Funnel counts for diagnostics."""

    fetched: int
    after_junk: int
    after_relevance: int
    after_dedup: int


def _normalize_pipeline(items: list[NewsItem]) -> tuple[list[NewsItem], NormalizeCounts]:
    fetched = len(items)

    cleaned: list[NewsItem] = []
    for item in items:
        snippet = clean_snippet(item.snippet)
        cleaned.append(item.model_copy(update={"snippet": snippet}))

    after_junk_list = [item for item in cleaned if not is_junk(item)]
    after_junk = len(after_junk_list)

    after_relevance_list = [item for item in after_junk_list if is_retail_relevant(item)]
    after_relevance = len(after_relevance_list)

    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    deduped: list[NewsItem] = []
    for item in after_relevance_list:
        url_key, title_key = dedup_key(item)
        if url_key and url_key in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue
        if url_key:
            seen_urls.add(url_key)
        if title_key:
            seen_titles.add(title_key)
        deduped.append(item)

    counts = NormalizeCounts(
        fetched=fetched,
        after_junk=after_junk,
        after_relevance=after_relevance,
        after_dedup=len(deduped),
    )
    return deduped, counts


def normalize_feed(items: list[NewsItem]) -> list[NewsItem]:
    """Clean snippets, drop junk/off-topic, dedupe by URL or title; preserve order."""
    normalized, _ = _normalize_pipeline(items)
    return normalized


def normalize_feed_with_counts(
    items: list[NewsItem],
) -> tuple[list[NewsItem], NormalizeCounts]:
    """Like normalize_feed but also returns funnel counts for logging."""
    return _normalize_pipeline(items)
