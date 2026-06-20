"""Tier-0 HTML parsing primitives shared by extractor + classifier + discovery.

Houses the price / currency / structural-signature primitive closure moved
out of ``app.modules.scraper.extractors`` in CLS1. Tier-0 invariant: imports
only stdlib + bs4; no upward imports of any Tier-1 module.

Cycle-break (CLS1 decision A): ``parse_price_text`` transitively pulls
``_detect_currency`` -> ``parse_currency_symbol`` / ``parse_currency_code``
-> ``_CURRENCY_SYMBOLS`` / ``_CURRENCY_TEXT_CODES`` plus
``_PRICE_CONTEXT_POSITIVE`` / ``_PRICE_CONTEXT_NEGATIVE`` /
``_MAX_REALISTIC_PRICE``. The whole closure lives here so both
classifier.service (Layer-3 price-density / repeated-structure) and
extractors.py (extraction strategies) can depend DOWN into it without
re-creating the extractor<->classifier cycle.
"""

from __future__ import annotations

import re


_CURRENCY_SYMBOLS: dict[str, str] = {
    "€": "EUR",
    "$": "USD",
    "£": "GBP",
    "₴": "UAH",
    "₽": "RUB",
    "zł": "PLN",
    "₺": "TRY",
    "₸": "KZT",
    "₾": "GEL",
    "₼": "AZN",
    "лв": "BGN",
    "kč": "CZK",
    "kr": "SEK",
    "ft": "HUF",
    "lei": "RON",
    "din": "RSD",
    "ден": "MKD",
    "сўм": "UZS",
    "сом": "KGS",
    "br": "BYN",
    "sm": "TJS",
}

# ISO codes mentioned as text near prices (case-insensitive match after a space).
_CURRENCY_TEXT_CODES: dict[str, str] = {
    "usd": "USD",
    "eur": "EUR",
    "gbp": "GBP",
    "uah": "UAH",
    "грн": "UAH",
    "rub": "RUB",
    "руб": "RUB",
    "р.": "RUB",
    "pln": "PLN",
    "ron": "RON",
    "try": "TRY",
    "tl": "TRY",
    "kzt": "KZT",
    "тг": "KZT",
    "тенге": "KZT",
    "byn": "BYN",
    "бел.руб": "BYN",
    "gel": "GEL",
    "azn": "AZN",
    "man": "AZN",
    "bgn": "BGN",
    "czk": "CZK",
    "sek": "SEK",
    "nok": "NOK",
    "dkk": "DKK",
    "huf": "HUF",
    "hrk": "HRK",
    "rsd": "RSD",
    "mdl": "MDL",
    "лей": "MDL",
    "лэй": "MDL",
    "chf": "CHF",
    "uzs": "UZS",
    "kgs": "KGS",
    "tjs": "TJS",
}

_PRICE_CONTEXT_POSITIVE = (
    "price",
    "цена",
    "стоимость",
    "total",
    "итого",
    "sale",
    "our price",
)
_PRICE_CONTEXT_NEGATIVE = (
    "%",
    "cashback",
    "кэшбэк",
    "bonus",
    "бонус",
    "скидка",
    "discount",
    "save",
    "эконом",
)

_MAX_REALISTIC_PRICE = 5_000_000.0
# Minimum count of structurally-identical elements to classify as a product grid.
REPEATED_STRUCTURE_MIN_COUNT = 6

_DATE_PATTERNS = (
    re.compile(r"\d{4}[-/.]\d{2}[-/.]\d{2}"),
    re.compile(r"\d{2}[-/.]\d{2}[-/.]\d{4}"),
)
_BARE_YEAR_RE = re.compile(r"^\d{4}$")


def _token_boundary_pattern(token: str) -> re.Pattern[str]:
    """Word-boundary regex for an alphabetic currency token (not substring match)."""
    return re.compile(
        r"(?<![\w])" + re.escape(token) + r"(?![\w])",
        re.IGNORECASE,
    )


def _number_overlaps_date_region(raw: str, start: int, end: int) -> bool:
    """True when *start:end* overlaps a YYYY-MM-DD / DD-MM-YYYY style date span."""
    for pattern in _DATE_PATTERNS:
        for date_match in pattern.finditer(raw):
            if start < date_match.end() and end > date_match.start():
                return True
    return False


def _is_bare_year_without_currency(token: str, context: str) -> bool:
    """Reject a standalone 4-digit year with no adjacent currency token."""
    stripped = token.strip()
    if not _BARE_YEAR_RE.fullmatch(stripped):
        return False
    year = int(stripped)
    if year < 1900 or year > 2099:
        return False
    return _detect_currency(context) is None


def parse_currency_symbol(text: str) -> str | None:
    """Detect currency ISO code from symbol characters in *text*.

    Single-char symbols (€, $, £) match by presence. Multi-char alphabetic
    symbols (kr, zł, lei) require a token boundary so substrings inside hashes
    do not match.
    """
    lowered = text.lower()
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if len(symbol) == 1:
            if symbol in text:
                return code
            continue
        if _token_boundary_pattern(symbol).search(lowered):
            return code
    return None


def parse_currency_code(text: str) -> str | None:
    """Detect currency ISO code from textual code / abbreviation near a price."""
    lowered = text.lower()
    for token, code in sorted(_CURRENCY_TEXT_CODES.items(), key=lambda item: -len(item[0])):
        if _token_boundary_pattern(token).search(lowered):
            return code
    return None


def _detect_currency(text: str) -> str | None:
    """Detect currency from symbols or textual codes embedded in *text*."""
    result = parse_currency_symbol(text)
    if result:
        return result
    return parse_currency_code(text)


def parse_price_text(text: str) -> float | None:
    """Parse price from text containing EU / CIS / Anglo-Saxon number formats.

    Supported patterns:
      1,234.56   (US/UK)         →  1234.56
      1.234,56   (DE/FR/RU/UA)   →  1234.56
      1 234,56   (RU/UA/KZ)      →  1234.56
      1 234.56   (rarely)        →  1234.56
      1234,56    (short EU)      →  1234.56
      1234.56    (plain)         →  1234.56
      1234       (integer)       →  1234.0
    """
    if not text:
        return None

    raw = str(text).strip()
    raw = raw.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    lowered = raw.lower()

    def _parse_number_token(token: str) -> float | None:
        value = token.strip()
        if not value:
            return None

        value = re.sub(r"\s*([,.])\s*", r"\1", value)
        has_comma = "," in value
        has_dot = "." in value
        has_space = " " in value

        if has_comma and has_dot:
            if value.rfind(",") > value.rfind("."):
                value = value.replace(" ", "").replace(".", "").replace(",", ".")
            else:
                value = value.replace(" ", "").replace(",", "")
        elif has_comma and not has_dot:
            parts = value.replace(" ", "").split(",")
            if len(parts) == 2 and len(parts[-1]) in (1, 2):
                value = value.replace(" ", "").replace(",", ".")
            elif len(parts) >= 2 and all(len(p) == 3 for p in parts[1:]):
                value = value.replace(" ", "").replace(",", "")
            else:
                last_part = parts[-1]
                if len(last_part) <= 2:
                    value = ",".join(parts[:-1]).replace(",", "") + "." + last_part
                    value = value.replace(" ", "")
                else:
                    value = value.replace(" ", "").replace(",", "")
        elif has_dot and not has_comma:
            parts = value.replace(" ", "").split(".")
            if len(parts) == 2 and len(parts[-1]) in (1, 2):
                value = value.replace(" ", "")
            elif len(parts) >= 2 and all(len(p) == 3 for p in parts[1:]):
                value = value.replace(" ", "").replace(".", "")
            else:
                value = value.replace(" ", "")
        elif has_space:
            value = value.replace(" ", "")

        try:
            number = float(value)
            return number if number > 0 else None
        except ValueError:
            return None

    candidates: list[tuple[float, int]] = []
    token_pattern = re.compile(r"\d{1,3}(?:[ \u00a0\u2009\u202f.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?")
    for match in token_pattern.finditer(raw):
        token = match.group(0)
        parsed = _parse_number_token(token)
        if parsed is None:
            continue

        start, end = match.span()
        if _number_overlaps_date_region(lowered, start, end):
            continue
        context = lowered[max(0, start - 20):min(len(lowered), end + 20)]
        if _is_bare_year_without_currency(token, context):
            continue
        score = 0
        if _detect_currency(context):
            score += 8
        if any(marker in context for marker in _PRICE_CONTEXT_POSITIVE):
            score += 4
        if any(marker in context for marker in _PRICE_CONTEXT_NEGATIVE):
            score -= 6
        if parsed < 1:
            score -= 3
        has_currency_context = _detect_currency(context) is not None
        if parsed > _MAX_REALISTIC_PRICE and not has_currency_context:
            continue
        if parsed > _MAX_REALISTIC_PRICE:
            score -= 20

        candidates.append((parsed, score))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[1], -item[0]))
    best_value = candidates[0][0]
    if best_value > _MAX_REALISTIC_PRICE:
        return None
    return best_value


def compute_element_signature(element) -> tuple[str, frozenset[str]]:
    """Return a structural signature for a BeautifulSoup element.

    Signature = (tag_name, frozenset_of_css_classes). Language-agnostic:
    CSS class names are treated as opaque tokens regardless of their meaning.

    Exposed under a public name (no leading underscore) for cross-module use
    by classifier.service Layer-3 and extractors.extract_links_from_repeated_structure.
    """
    tag = getattr(element, "name", "") or ""
    classes: list[str] = element.get("class", []) if hasattr(element, "get") else []
    return (tag.lower(), frozenset(classes))


# Back-compat alias for any existing call sites that already used the
# underscored name.
_compute_element_signature = compute_element_signature


__all__ = [
    "REPEATED_STRUCTURE_MIN_COUNT",
    "parse_price_text",
    "parse_currency_symbol",
    "parse_currency_code",
    "_detect_currency",
    "compute_element_signature",
    "_compute_element_signature",
    "_CURRENCY_SYMBOLS",
    "_CURRENCY_TEXT_CODES",
    "_PRICE_CONTEXT_POSITIVE",
    "_PRICE_CONTEXT_NEGATIVE",
    "_MAX_REALISTIC_PRICE",
]
