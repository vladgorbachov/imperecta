"""Match-signature extraction — Python reference implementation.

The Rust twin lives in rust_core/src/matching.rs (module imperecta_core,
function extract_match_signature); both implementations MUST stay in
byte-for-byte agreement — the facade below prefers Rust when built and
EXTRACTOR_ENGINE=rust, and tests/test_matching_signature.py pins the
contract with live-pool examples.

Design (docs/MATCHING_PLAN.md, slice M1): a product is matchable across
shops when its normalized name yields BOTH a brand token and a model code.
Model codes are language-invariant ASCII (titles differ per country, codes
do not), which is why they beat title-similarity as the primary key.
"""

from __future__ import annotations

import os
import re
import uuid

try:  # Rust extraction core (backend/rust_core) — optional until built
    import imperecta_core as _rust_core
except ImportError:  # pragma: no cover - depends on build environment
    _rust_core = None

# Deterministic group-id namespace: uuid5 over "brand|code" means every
# incremental run converges to the same group ids with no group table and
# no cross-run coordination (permanent-pool policy).
MATCH_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "match.imperecta.com")

CONFIDENCE_KNOWN_BRAND = 0.90
CONFIDENCE_HEURISTIC_BRAND = 0.75

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Measurement/quantity tokens: attributes of a product, never a model code.
_UNIT_RE = re.compile(
    r"^\d+(?:gb|tb|mb|kb|mm|cm|km|kg|mg|ml|cl|dl|l|g|m|w|kw|mw|v|kv|mv|a|ah|"
    r"mah|hz|ghz|mhz|khz|k|p|mp|px|dpi|in|inch|cal|kcal|szt|gab|vnt|tk|pcs|"
    r"db|bar|rpm|lm|lux|nm|ns|ms|s|min|h|x|d|fps|bit|mbps|gbps|ppm|denier)$",
)
_DIMENSIONS_RE = re.compile(r"^\d+x\d+(?:x\d+)?[a-z]*$")

# Tokens that are artifacts of slug-derived names, never brand or code.
_STOPWORDS = frozenset({"html", "bhtml", "htm", "php", "aspx", "www", "com"})

_PURE_DIGIT_MIN = 5
_PURE_DIGIT_MAX = 9
_MIXED_MIN_LEN = 4
_JOINED_MIN_LEN = 5


def _is_unit_token(token: str) -> bool:
    return bool(_UNIT_RE.match(token) or _DIMENSIONS_RE.match(token))


def _is_alpha(token: str) -> bool:
    return token.isalpha()


def _is_mixed(token: str) -> bool:
    return (not token.isalpha()) and (not token.isdigit())


def extract_match_signature(
    name_normalized: str | None,
    known_brands: frozenset[str] | set[str],
) -> dict | None:
    """Extract {brand, code, codes, attrs, confidence} or None (unmatchable).

    Requires both a brand token and at least one model code — junk
    slug-names (pure digits, "pb00613262.html") fail one of the two and
    land in 'unmatched' instead of poisoning groups.
    """
    if not name_normalized:
        return None
    tokens = _TOKEN_RE.findall(name_normalized.lower())
    if not tokens:
        return None

    attrs: list[str] = []
    codes: list[str] = []
    seen_codes: set[str] = set()

    def _add_code(code: str) -> None:
        if code not in seen_codes:
            seen_codes.add(code)
            codes.append(code)

    for token in tokens:
        if token in _STOPWORDS:
            continue
        if _is_unit_token(token):
            attrs.append(token)
            continue
        if _is_mixed(token) and len(token) >= _MIXED_MIN_LEN:
            _add_code(token)
        elif token.isdigit() and _PURE_DIGIT_MIN <= len(token) <= _PURE_DIGIT_MAX:
            # Style/article numbers (e.g. Under Armour 1109226): weak codes —
            # shop-internal ids only cost recall, never precision, because a
            # group still requires the brand token to agree.
            _add_code(token)

    # Neighbor joins: "galaxy s24" -> "galaxys24", "sfd 950ss" -> "sfd950ss".
    # Same trick as numeric_edge_tokens in listing_page: shops disagree on
    # where the space goes inside a model name; the joined form does not.
    # Never join off a brand-position token (known brand, or the first
    # alphabetic token): "sencor sfd950ss" must not mint "sencorsfd950ss"
    # while "sencor sfd 950ss" mints "sfd950ss" — the keys would diverge.
    first_alpha = next(
        (t for t in tokens if _is_alpha(t) and t not in _STOPWORDS), None
    )
    for left, right in zip(tokens, tokens[1:]):
        if not (_is_alpha(left) and len(left) >= 2 and left not in _STOPWORDS):
            continue
        if left in known_brands or left == first_alpha:
            continue
        if _is_unit_token(right) or right in _STOPWORDS:
            continue
        if not (right[0].isdigit() or _is_mixed(right)):
            continue
        joined = left + right
        if len(joined) >= _JOINED_MIN_LEN and not _is_unit_token(joined):
            _add_code(joined)

    if not codes:
        return None

    brand: str | None = None
    confidence = CONFIDENCE_HEURISTIC_BRAND
    for token in tokens:
        if token in known_brands:
            brand = token
            confidence = CONFIDENCE_KNOWN_BRAND
            break
    if brand is None:
        for token in tokens:
            if _is_alpha(token) and len(token) >= 3 and token not in _STOPWORDS:
                brand = token
                break
    if brand is None:
        return None

    # Strongest code: mixed beats pure-digit (more entropy), then longest,
    # then lexicographic — fully deterministic across runs and languages.
    strongest = sorted(codes, key=lambda c: (not _is_mixed(c), -len(c), c))[0]
    return {
        "brand": brand,
        "code": strongest,
        "codes": codes,
        "attrs": attrs,
        "confidence": confidence,
    }


def match_group_id(brand: str, code: str) -> uuid.UUID:
    """Deterministic cross-run group id for a (brand, strongest code) key."""
    return uuid.uuid5(MATCH_NAMESPACE, f"{brand}|{code}")


def _use_rust() -> bool:
    return (
        _rust_core is not None
        and hasattr(_rust_core, "extract_match_signature")
        and os.getenv("EXTRACTOR_ENGINE", "python").strip().lower() == "rust"
    )


def extract_signature(
    name_normalized: str | None,
    known_brands: frozenset[str] | set[str],
) -> dict | None:
    """Engine-dispatching facade (EXTRACTOR_ENGINE=rust -> compiled core)."""
    if _use_rust():
        return _rust_core.extract_match_signature(name_normalized, list(known_brands))
    return extract_match_signature(name_normalized, known_brands)
