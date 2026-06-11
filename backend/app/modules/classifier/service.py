"""Page-role classification — Layers 1/2/2.5/3.

Moved verbatim from ``app.modules.scraper.extractors`` in CLS1.

Layer 1: Open Graph ``og:type`` (single-value page-level meta tag).
Layer 2: JSON-LD top-level ``@type`` (schema.org page declaration).
Layer 2.5: HTML5 Microdata top-level ``itemtype`` (schema.org via Microdata).
Layer 3: Structural fallback (repeated-DOM-structure count + price density);
         uses the Tier-0 primitives ``parse_price_text`` /
         ``compute_element_signature`` / ``REPEATED_STRUCTURE_MIN_COUNT``.

The classifier imports DOWN only:
    - app.common.html_parsing (Tier-0 primitives)
    - stdlib + bs4

It imports NOTHING from extractor / discovery / scraper / ingestion.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Literal

from bs4 import BeautifulSoup

from app.common.html_parsing import (
    REPEATED_STRUCTURE_MIN_COUNT,
    compute_element_signature,
    parse_price_text,
)
from app.modules.classifier.constants import (
    _JSONLD_TYPES_HUB,
    _JSONLD_TYPES_LISTING,
    _JSONLD_TYPES_PRODUCT,
    _MICRODATA_TYPES_LISTING,
    _MICRODATA_TYPES_PRODUCT,
    _OG_TYPES_HUB,
    _OG_TYPES_LISTING,
    _OG_TYPES_PRODUCT,
)

PageRole = Literal["product", "listing", "hub", "unknown"]


def classify_page_role(soup: BeautifulSoup, base_url: str) -> str:
    """Classify a fetched page as 'listing', 'product', 'hub', or 'unknown'.

    Uses three language-agnostic signals:
    1. Schema.org JSON-LD @type annotation (most reliable).
    2. Repeated DOM structure count (listing signal).
    3. Price density - count of parseable prices on the page.

    Returns one of: 'listing', 'product', 'hub', 'unknown'.
    """
    for script_tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script_tag.string or "")
            if isinstance(data, list):
                data = data[0] if data else {}
            page_type = data.get("@type", "")
            if isinstance(page_type, list):
                page_type = page_type[0] if page_type else ""
            if page_type == "Product":
                return "product"
            if page_type in ("ItemList", "OfferCatalog", "CollectionPage"):
                return "listing"
            if page_type in ("WebSite", "Organization", "BreadcrumbList"):
                pass
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue

    signature_counts: dict[tuple, int] = defaultdict(int)
    for element in soup.find_all(True):
        sig = compute_element_signature(element)
        if sig[0] and sig[1]:
            signature_counts[sig] += 1
    max_repetition = max(signature_counts.values()) if signature_counts else 0
    has_product_grid = max_repetition >= REPEATED_STRUCTURE_MIN_COUNT

    price_count = 0
    for text_node in soup.find_all(string=True):
        text = str(text_node).strip()
        if len(text) <= 1:
            continue
        parsed_price = parse_price_text(text)
        if parsed_price is not None and 0 < parsed_price < 9_999_999:
            price_count += 1

    if has_product_grid and price_count >= REPEATED_STRUCTURE_MIN_COUNT:
        return "listing"
    if price_count == 0 and max_repetition < REPEATED_STRUCTURE_MIN_COUNT:
        return "hub"
    if 1 <= price_count <= 5 and not has_product_grid:
        return "product"
    if has_product_grid:
        return "listing"
    return "unknown"


def _get_og_type(soup: BeautifulSoup) -> str | None:
    """Return lowercased Open Graph og:type from the page, or None if absent.

    Open Graph is a single-value page-level meta tag set by site authors for
    social-network preview, e.g. <meta property="og:type" content="product">.
    """
    meta = soup.find("meta", attrs={"property": "og:type"})
    if meta is None:
        return None
    content = meta.get("content")
    if not isinstance(content, str):
        return None
    cleaned = content.strip().lower()
    return cleaned or None


def _get_jsonld_root_types(soup: BeautifulSoup) -> set[str]:
    """Return the set of top-level @type values from all JSON-LD scripts on the page.

    Handles three structural cases:
    - JSON-LD root is a dict with @type: string or list of strings.
    - JSON-LD root is a list of such dicts.
    - JSON-LD is malformed → silently skip that script tag.

    Nested @types (e.g. inside `offers`, `aggregateRating`) are intentionally
    NOT collected: they describe sub-entities of a parent object, not the
    page as a whole.
    """
    types: set[str] = set()
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or ""
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            if not isinstance(item, dict):
                continue
            type_value = item.get("@type")
            if isinstance(type_value, str):
                types.add(type_value)
            elif isinstance(type_value, list):
                for sub in type_value:
                    if isinstance(sub, str):
                        types.add(sub)
    return types


def _get_microdata_toplevel_types(soup: BeautifulSoup) -> set[str]:
    """Return itemtype values from top-level itemscope elements only.

    "Top-level" means the element has no ancestor with `itemscope` attribute.
    This excludes nested Product cards inside an ItemList (category page),
    or nested ListItem inside a BreadcrumbList. Such nested types describe
    components of the page, not the page's role itself.

    Returns the itemtype URL set (e.g., {"http://schema.org/Product"}).
    Values are returned as-is, without case normalization, since schema.org
    URLs are always lowercase by convention and our constant sets follow
    the same convention.
    """
    result: set[str] = set()
    for tag in soup.find_all(attrs={"itemtype": True}):
        has_outer_itemscope = False
        parent = tag.parent
        while parent is not None:
            if getattr(parent, "attrs", None) is not None and "itemscope" in parent.attrs:
                has_outer_itemscope = True
                break
            parent = parent.parent
        if has_outer_itemscope:
            continue
        itemtype_value = (tag.get("itemtype") or "").strip()
        if itemtype_value:
            result.add(itemtype_value)
    return result


def classify_page_role_for_discovery(soup: BeautifulSoup, base_url: str) -> str:
    """Discovery-targeted page role classification using structured-data signals.

    Returns one of: 'product', 'listing', 'hub', 'unknown'.

    Strategy — three layers, from most to least reliable:

    Layer 1: Open Graph og:type. A single-value page-level meta tag explicitly
    set by site authors for social-network previews. Strong, unambiguous signal:
      - og:type in _OG_TYPES_PRODUCT  → 'product'
      - og:type in _OG_TYPES_HUB      → 'hub'
      - og:type in _OG_TYPES_LISTING  → 'listing'  (article/blog/news grouped
        with listing because they are non-product content pages; this is a
        deliberate design choice, not a bug)
      - any other og:type value       → fall through to Layer 2

    Layer 2: JSON-LD top-level @type. The site author's schema.org declaration
    of what the page represents. If multiple types appear, Product wins over
    listing-coexisting types (a PDP can include a Breadcrumb in JSON-LD without
    being a listing). Otherwise, listing/hub mapping is taken from the
    corresponding _JSONLD_TYPES_* sets.

    Layer 3: Fallback to existing classify_page_role(). Handles sites that emit
    no structured data — rare on modern e-commerce but possible on small/legacy
    shops. The existing function is more conservative (tuned for extractor use),
    but its 'unknown' result is preserved as 'unknown' here, not silently
    promoted to 'listing'.

    This function intentionally ignores repeated-DOM-structure signals on layers
    1 and 2: related-product blocks on a real PDP would trigger them, leading
    to false 'listing' classification (which is exactly the bug this function
    fixes for discovery).
    """
    # Layer 1: Open Graph
    og_type = _get_og_type(soup)
    if og_type is not None:
        if og_type in _OG_TYPES_PRODUCT:
            return "product"
        if og_type in _OG_TYPES_HUB:
            return "hub"
        if og_type in _OG_TYPES_LISTING:
            return "listing"
        # Other og:type values (profile, book, music, video) → fall through.

    # Layer 2: JSON-LD
    ld_types = _get_jsonld_root_types(soup)
    if ld_types:
        if ld_types & _JSONLD_TYPES_PRODUCT:
            # Product wins over coexisting listing-like types (PDP + Breadcrumb).
            return "product"
        if ld_types & _JSONLD_TYPES_LISTING:
            return "listing"
        if ld_types & _JSONLD_TYPES_HUB:
            return "hub"
        # Other JSON-LD types → fall through to structural fallback.

    # Layer 2.5: HTML5 Microdata via itemscope/itemtype attributes.
    # Some sites emit schema.org via Microdata only, without og:type or JSON-LD.
    # We look at top-level itemtype only (not nested) so that:
    #   - A PDP with a "Related products" ItemList block remains 'product'
    #     (Product on top-level + ItemList for related → Product wins).
    #   - A pure category page (only ItemList/OfferCatalog top-level, with
    #     nested Product cards) is 'listing'.
    md_top_types = _get_microdata_toplevel_types(soup)
    if md_top_types:
        if md_top_types & _MICRODATA_TYPES_PRODUCT:
            return "product"
        if md_top_types & _MICRODATA_TYPES_LISTING:
            return "listing"
        # Other Microdata top-level types → fall through to Layer 3.

    # Layer 3: structural fallback
    return classify_page_role(soup, base_url)


__all__ = [
    "PageRole",
    "classify_page_role",
    "classify_page_role_for_discovery",
    "_get_og_type",
    "_get_jsonld_root_types",
    "_get_microdata_toplevel_types",
]
