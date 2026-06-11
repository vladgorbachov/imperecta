"""
Universal product data extraction from HTML.
No marketplace-specific selectors. Works on any e-commerce site.

Extraction levels (in priority order):
1. JSON-LD (Schema.org Product) - most reliable, ~80% of sites
2. OpenGraph / meta tags - og:title, og:image, product:price
3. Custom CSS selectors from DB (if marketplace has them configured)
4. Auto-detect heuristics - currency patterns, h1 title, largest image
"""

import json
import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.common.html_parsing import (
    REPEATED_STRUCTURE_MIN_COUNT,
    _CURRENCY_SYMBOLS,
    _CURRENCY_TEXT_CODES,
    _MAX_REALISTIC_PRICE,
    _PRICE_CONTEXT_NEGATIVE,
    _PRICE_CONTEXT_POSITIVE,
    _compute_element_signature,
    _detect_currency,
    compute_element_signature,
    parse_currency_code,
    parse_currency_symbol,
    parse_price_text,
)
from app.modules.classifier import (
    classify_page_role,
    classify_page_role_for_discovery,
)

logger = logging.getLogger(__name__)

# Max chars stored for debug/raw extraction traces (avoid huge strings in logs).
_MAX_TITLE_LEN = 1000

# Re-export the moved primitives so legacy imports
#   ``from app.modules.scraper.extractors import parse_price_text``
# keep resolving. Canonical home is app.common.html_parsing (CLS1).
__all__ = [
    "_CURRENCY_SYMBOLS",
    "_CURRENCY_TEXT_CODES",
    "_MAX_REALISTIC_PRICE",
    "_PRICE_CONTEXT_NEGATIVE",
    "_PRICE_CONTEXT_POSITIVE",
    "REPEATED_STRUCTURE_MIN_COUNT",
    "_compute_element_signature",
    "_detect_currency",
    "compute_element_signature",
    "parse_currency_code",
    "parse_currency_symbol",
    "parse_price_text",
    "classify_page_role",
    "classify_page_role_for_discovery",
]

_EXCLUDED_LINK_HINTS = (
    "login",
    "signin",
    "signup",
    "register",
    "cart",
    "basket",
    "checkout",
    "wishlist",
    "filter",
    "sort",
    "category",
    "catalog",
    "search",
    "account",
    "compare",
    "help",
    "faq",
    "about",
    "contact",
    "blog",
    "news",
    "privacy",
    "terms",
    "return",
    "delivery",
    "shipping",
    "brands",
    "seller",
    "magazin",
    "otzyvy",
    "/reviews",
)

_PRODUCT_LINK_HINTS = (
    "/product/",
    "/products/",
    "/item/",
    "/p/",
    "/tovar/",
    "/dp/",
    "/catalog/product/",
    "/detail/",
    "/offer/",
    "/sku/",
)

_CATALOG_NUMERIC_PRODUCT_PATH_RE = re.compile(
    r"/(?:catalog|detail)/\d{4,}"
    r"|/(?:product|tovar|sku)/[\w-]{4,}"
    r"|/p/\d+",
)

# Path segments that indicate category/listing page, not product
_CATEGORY_PATH_SEGMENTS = (
    "catalog",
    "c",
    "category",
    "shop",
    "categories",
    "katalog",
    "collection",
    "collections",
    "promo",
    "sale",
    "akcii",
    "rasprodazha",
    "new",
    "novinki",
    "top",
    "best",
    "popular",
)
# Maximum number of sitemap sub-files to follow from a sitemap index.
SITEMAP_MAX_SUBFILES = 15
# Maximum product URLs to harvest from a single sitemap (memory guard).
SITEMAP_MAX_URLS = 50_000
# Maximum depth of BFS site crawl for category recon.
CATEGORY_RECON_MAX_DEPTH = 3


@dataclass
class ExtractedProduct:
    """Unified extraction result."""

    title: str | None = None
    price: float | None = None
    original_price: float | None = None
    currency: str | None = None
    image_url: str | None = None
    description: str | None = None
    price_raw_text: str | None = None
    currency_raw: str | None = None

    @property
    def completeness(self) -> float:
        """Fraction of required fields filled (0.0 to 1.0)."""
        required = ["title", "price", "image_url"]
        filled = sum(1 for field_name in required if getattr(self, field_name) is not None)
        return filled / len(required)

    @property
    def missing_fields(self) -> list[str]:
        required = ["title", "price", "image_url"]
        return [field_name for field_name in required if getattr(self, field_name) is None]


def _fallback_title_from_page(soup: BeautifulSoup, page_url: str = "") -> str | None:
    """Derive a non-empty title when Product name / og:title are absent."""
    if soup.title and soup.title.string:
        raw = soup.title.string.strip()
        if raw:
            for sep in ("|", "—", "-"):
                if sep in raw:
                    raw = raw.split(sep, 1)[0].strip()
                    break
            if raw:
                return raw[:_MAX_TITLE_LEN]
    h1 = soup.find("h1")
    if h1:
        t = h1.get_text(strip=True)
        if t:
            return t[:_MAX_TITLE_LEN]
    if page_url:
        parsed = urlparse(page_url)
        segments = [s for s in parsed.path.split("/") if s]
        if segments:
            last = segments[-1].replace("-", " ").replace("_", " ").strip()
            if last and len(last) > 2:
                return last[:_MAX_TITLE_LEN]
    return None


def _ensure_title(ep: ExtractedProduct, soup: BeautifulSoup, page_url: str = "") -> None:
    """Guarantee title is set when the DOM offers any reasonable fallback."""
    cur = getattr(ep, "title", None)
    if cur is not None and str(cur).strip():
        return
    fb = _fallback_title_from_page(soup, page_url)
    if fb:
        ep.title = fb


def _find_product_nodes(item: dict) -> list[dict]:
    nodes: list[dict] = []
    node_type = item.get("@type")
    if isinstance(node_type, list):
        if any(str(t).lower() == "product" for t in node_type):
            nodes.append(item)
    elif str(node_type).lower() == "product":
        nodes.append(item)

    graph = item.get("@graph")
    if isinstance(graph, list):
        for node in graph:
            if not isinstance(node, dict):
                continue
            gtype = node.get("@type")
            if isinstance(gtype, list):
                if any(str(t).lower() == "product" for t in gtype):
                    nodes.append(node)
            elif str(gtype).lower() == "product":
                nodes.append(node)
    return nodes


def extract_from_jsonld(soup: BeautifulSoup, page_url: str = "") -> ExtractedProduct:
    """Level 1: JSON-LD."""
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            parsed = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue

        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            if not isinstance(item, dict):
                continue
            for product in _find_product_nodes(item):
                offers = product.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                if isinstance(offers, str):
                    offers = {}
                if not isinstance(offers, dict):
                    offers = {}

                price = None
                original_price = None
                raw_price: str | None = None
                if "price" in offers:
                    raw_price = str(offers.get("price"))[:500]
                    price = parse_price_text(raw_price)
                elif "lowPrice" in offers:
                    raw_price = str(offers.get("lowPrice"))[:500]
                    price = parse_price_text(raw_price)
                    if "highPrice" in offers:
                        original_price = parse_price_text(str(offers.get("highPrice")))
                elif "highPrice" in offers:
                    raw_price = str(offers.get("highPrice"))[:500]
                    price = parse_price_text(raw_price)

                image = product.get("image")
                if isinstance(image, list):
                    image = image[0] if image else None
                elif isinstance(image, dict):
                    image = image.get("url")

                description = product.get("description")
                if isinstance(description, str) and len(description) > 2000:
                    description = description[:2000]

                currency_src = offers.get("priceCurrency") if isinstance(offers, dict) else None
                currency = None
                currency_raw_val: str | None = None
                if isinstance(currency_src, str) and currency_src.strip():
                    currency_raw_val = currency_src.strip()[:20]
                    currency = currency_src.strip().upper()[:3]

                ep = ExtractedProduct(
                    title=product.get("name"),
                    price=price,
                    original_price=original_price,
                    currency=currency,
                    image_url=image if isinstance(image, str) else None,
                    description=description if isinstance(description, str) else None,
                    price_raw_text=raw_price,
                    currency_raw=currency_raw_val,
                )
                _ensure_title(ep, soup, page_url)
                return ep
    ep = ExtractedProduct()
    _ensure_title(ep, soup, page_url)
    return ep


def extract_from_meta_tags(soup: BeautifulSoup, page_url: str = "") -> ExtractedProduct:
    """Level 2: OpenGraph + meta."""
    result = ExtractedProduct()
    price_props = [
        ("og:price:amount", "og:price:currency"),
        ("product:price:amount", "product:price:currency"),
        ("twitter:data1", None),
    ]
    for price_prop, currency_prop in price_props:
        node = soup.find("meta", property=price_prop) or soup.find(
            "meta",
            attrs={"name": price_prop},
        )
        if not node or not node.get("content"):
            continue
        raw_meta = str(node["content"]).strip()[:500]
        parsed = parse_price_text(raw_meta)
        if parsed is None:
            continue
        result.price = parsed
        result.price_raw_text = raw_meta
        if currency_prop:
            cur = soup.find("meta", property=currency_prop) or soup.find(
                "meta",
                attrs={"name": currency_prop},
            )
            if cur and cur.get("content"):
                result.currency_raw = str(cur.get("content")).strip()[:20]
                result.currency = str(cur.get("content")).strip().upper()[:3]
        if result.currency is None and result.price is not None:
            result.currency = _detect_currency(raw_meta)
            if result.currency:
                result.currency_raw = raw_meta
        break

    for prop in ["og:title", "twitter:title"]:
        node = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if node and node.get("content"):
            result.title = str(node["content"]).strip()[:1000]
            break

    for prop in ["og:image", "twitter:image"]:
        node = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if node and node.get("content"):
            result.image_url = str(node["content"]).strip()
            break

    desc = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta",
        property="og:description",
    )
    if desc and desc.get("content"):
        result.description = str(desc["content"]).strip()[:2000]

    _ensure_title(result, soup, page_url)
    return result


def extract_with_custom_selectors(
    soup: BeautifulSoup,
    selectors: dict,
    page_url: str = "",
) -> ExtractedProduct:
    """
    Level 3 (optional): Custom CSS selectors from dim_marketplace (or listing scraper_config).
    selectors keys: "title", "price", "image", "original_price"
    """
    result = ExtractedProduct()

    title_selector = selectors.get("title")
    if title_selector:
        element = soup.select_one(title_selector)
        if element:
            result.title = element.get_text(strip=True)[:1000]

    price_selector = selectors.get("price")
    if price_selector:
        element = soup.select_one(price_selector)
        if element:
            raw_px = element.get_text(strip=True)[:500]
            parsed_px = parse_price_text(raw_px)
            result.price = parsed_px
            if parsed_px is not None:
                result.price_raw_text = raw_px

    image_selector = selectors.get("image")
    if image_selector:
        element = soup.select_one(image_selector)
        if element:
            src = element.get("src") or element.get("data-src")
            if src:
                result.image_url = str(src).strip()

    original_selector = selectors.get("original_price")
    if original_selector:
        element = soup.select_one(original_selector)
        if element:
            result.original_price = parse_price_text(element.get_text(strip=True))

    _ensure_title(result, soup, page_url)
    return result


def extract_auto_detect(soup: BeautifulSoup, url: str = "") -> ExtractedProduct:
    """Level 4: Auto-detect using universal heuristics."""
    result = ExtractedProduct()

    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
        if title:
            result.title = title[:1000]
    if not result.title and soup.title and soup.title.string:
        raw_title = soup.title.string.strip()
        for sep in ("|", "—", "-"):
            if sep in raw_title:
                raw_title = raw_title.split(sep, 1)[0].strip()
                break
        if raw_title:
            result.title = raw_title[:1000]

    candidates: list[tuple[int, str]] = []
    for tag in soup.find_all(["span", "div", "p", "strong", "meta"]):
        text = ""
        if tag.name == "meta":
            content = tag.get("content")
            text = str(content).strip() if content else ""
        else:
            text = tag.get_text(strip=True)
        if not text:
            continue
        if parse_price_text(text) is None:
            continue
        attrs = " ".join(
            [
                str(tag.get("class", "")),
                str(tag.get("id", "")),
                str(tag.get("itemprop", "")),
            ]
        ).lower()
        score = 0
        if "price" in attrs:
            score += 10
        if "current" in attrs or "final" in attrs:
            score += 5
        if any(sym in text.lower() for sym in _CURRENCY_SYMBOLS):
            score += 3
        candidates.append((score, text))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        best = candidates[0][1]
        parsed = parse_price_text(best)
        result.price = parsed
        if parsed is not None:
            result.price_raw_text = best[:500]
            detected = _detect_currency(best)
            if detected:
                result.currency = detected
                result.currency_raw = best[:100]

    best_img_url = None
    best_img_area = -1
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue
        attrs = " ".join(
            [
                str(img.get("class", "")),
                str(img.get("id", "")),
                str(img.get("alt", "")),
            ]
        ).lower()
        width = int(img.get("width")) if str(img.get("width", "")).isdigit() else 0
        height = int(img.get("height")) if str(img.get("height", "")).isdigit() else 0
        area = width * height
        if "product" in attrs or "gallery" in attrs:
            area += 1000000
        if area > best_img_area:
            best_img_area = area
            best_img_url = str(src).strip()
    if best_img_url:
        result.image_url = urljoin(url, best_img_url) if url else best_img_url

    if not result.description:
        desc = soup.find("meta", attrs={"name": "description"}) or soup.find(
            "meta",
            property="og:description",
        )
        if desc and desc.get("content"):
            result.description = str(desc["content"]).strip()[:2000]

    _ensure_title(result, soup, url)
    return result


def merge_results(*results: ExtractedProduct) -> ExtractedProduct:
    """Merge multiple extraction results. First non-None value wins."""
    merged = ExtractedProduct()
    for field_name in [
        "title",
        "price",
        "original_price",
        "currency",
        "image_url",
        "description",
        "price_raw_text",
        "currency_raw",
    ]:
        for result in results:
            value = getattr(result, field_name, None)
            if value is not None:
                setattr(merged, field_name, value)
                break
    return merged


def merge_and_finalize(
    soup: BeautifulSoup,
    page_url: str,
    *results: ExtractedProduct,
) -> ExtractedProduct:
    """Merge extractor outputs and ensure title fallback from the full DOM."""
    page_role = classify_page_role_for_discovery(soup, page_url)
    if page_role in ("listing", "hub"):
        logger.info(
            "merge_skipped_non_pdp_page page_url=%s page_role=%s",
            page_url[:200],
            page_role,
        )
        return ExtractedProduct()

    merged = merge_results(*results)
    if merged.currency is None:
        if merged.price_raw_text:
            detected = _detect_currency(merged.price_raw_text)
            if detected:
                merged.currency = detected
                merged.currency_raw = merged.price_raw_text[:100]
        if merged.currency is None and merged.price is not None:
            text_probe = soup.get_text(" ", strip=True)[:4000]
            detected = _detect_currency(text_probe)
            if detected:
                merged.currency = detected
                merged.currency_raw = text_probe[:100]
    _ensure_title(merged, soup, page_url)
    logger.debug(
        "EXTRACTED title=%s price=%s currency=%s",
        merged.title,
        merged.price,
        merged.currency,
    )
    return merged


def _looks_like_product_url(path: str) -> bool:
    """Product URLs: .html, product hints, CIS SKU patterns, 4+ digit IDs, or 3+ segments."""
    lowered = path.lower()
    if any(hint in lowered for hint in _PRODUCT_LINK_HINTS):
        return True
    if _CATALOG_NUMERIC_PRODUCT_PATH_RE.search(lowered):
        return True
    if re.search(r"/\d{4,}", lowered):
        return True
    if ".html" in lowered:
        return True
    segments = [s for s in lowered.split("/") if s]
    if len(segments) >= 3:
        return True
    return False


def _looks_like_product_slug(segment: str) -> bool:
    """Strong heuristic: does this single URL path segment look like a PDP slug?

    Three positive signals (any one is sufficient):
    1. Segment ends with .html or .htm — universal PDP convention on legacy
       and CMS-driven sites.
    2. Segment contains a dash-prefixed run of 6+ digits — common pattern
       like `iphone-15-pro-12345678` or `product-name-11000225`. The dash
       before the digits distinguishes a product ID embedded in a slug from
       a year suffix on a category name (e.g. `summer-2024`, which is 4 digits
       and not 6+).
    3. Segment is a standalone run of 6+ digits — common pattern for
       numeric-id PDPs like `/p/12345678` or `/dp/12345678`.

    The 6-digit minimum is chosen to exclude common year-suffixes (4 digits)
    and short numeric category IDs (e.g. `c80004` has 5 digits without a dash
    separator, correctly classified as NOT a product slug).
    """
    if not segment:
        return False
    lowered = segment.lower()
    if lowered.endswith(".html") or lowered.endswith(".htm"):
        return True
    if re.search(r"-\d{6,}(?:[-/_.]|$)", lowered):
        return True
    if re.fullmatch(r"\d{6,}", lowered):
        return True
    return False


def _is_category_url(path: str) -> bool:
    """Exclude category/listing URLs. Product pages have more specific paths.

    Improved logic (defence-in-depth, complements schema-aware classifier):
    - Single-segment paths default to category (homepage / `/catalog` / `/sale`)
      unless the segment itself looks like a long product slug.
    - For multi-segment paths, the LAST path segment is inspected first:
      if it looks like a product slug (see _looks_like_product_slug), this
      is a PDP-inside-category URL (e.g. `/catalog/electronics/iphone-12345678`),
      NOT a category, even when path contains a category-word like `catalog`.
    - Otherwise, presence of a category-word segment is the deciding signal.
    """
    lowered = path.lower()
    segments = [s for s in lowered.split("/") if s]
    if len(segments) <= 1:
        if segments:
            single = segments[0]
            if len(single) >= 16 and ("-" in single or any(ch.isdigit() for ch in single)):
                return False
        return True

    # Strong PDP signal in the last segment overrides category-word presence
    # elsewhere in path. This fixes the false-positive on `/catalog/{cat}/{slug}`
    # schemes where the product slug carries a 6+ digit product ID.
    last = segments[-1]
    if _looks_like_product_slug(last):
        return False

    if any(seg in _CATEGORY_PATH_SEGMENTS for seg in segments):
        return True
    if ".html" in lowered:
        return False
    if re.search(r"\d{4,}", lowered):
        return False
    if len(segments) == 3 and segments[-1] and len(segments[-1]) < 15:
        return True
    return False


def _is_excluded_link(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in _EXCLUDED_LINK_HINTS)


def extract_product_links(
    soup: BeautifulSoup,
    base_url: str,
    custom_selector: str | None = None,
) -> list[str]:
    """Extract product URLs from category/listing page. Strict filtering excludes category URLs."""
    links = []
    if custom_selector:
        links = soup.select(custom_selector)
    else:
        links = soup.find_all("a", href=True)

    parsed_base = urlparse(base_url)
    collected: list[str] = []
    seen: set[str] = set()
    for link in links:
        href = link.get("href")
        if not href:
            continue
        full_url = urljoin(base_url, href.strip())
        parsed = urlparse(full_url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc != parsed_base.netloc:
            continue
        if _is_excluded_link(full_url):
            continue
        if _is_category_url(parsed.path):
            continue
        if not _looks_like_product_url(parsed.path):
            continue
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if len(normalized) > 2000:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        collected.append(normalized)

    filtered: list[str] = []
    for url in collected:
        path = urlparse(url).path.lower()
        if "/list/" in path:
            continue
        if "/category/" in path and not re.search(r"/\d{4,}", path):
            continue
        if "/catalog/" in path and not re.search(r"/\d{4,}", path):
            continue
        if "/search" in path:
            continue
        if path.endswith("/") and path.count("/") <= 3:
            continue
        if re.search(r"/\d{5,}", path):
            filtered.append(url)
            continue
        if ".html" in path:
            filtered.append(url)
            continue
        if re.search(r"[-_]\d{4,}", path):
            filtered.append(url)
            continue
        if "/p/" in path or "/product/" in path or "/tovar/" in path:
            filtered.append(url)
            continue
        segments = [s for s in path.split("/") if s]
        if len(segments) >= 4:
            filtered.append(url)
            continue
        if len(segments) >= 2:
            last = segments[-1]
            if len(last) >= 18 and "-" in last:
                filtered.append(url)
    return filtered


def detect_next_page(
    soup: BeautifulSoup,
    current_url: str,
    custom_selector: str | None = None,
) -> str | None:
    """Find next page URL for pagination."""
    if custom_selector:
        node = soup.select_one(custom_selector)
        if node and node.get("href"):
            return urljoin(current_url, str(node.get("href")).strip())

    rel_next = soup.find("link", rel="next")
    if rel_next and rel_next.get("href"):
        return urljoin(current_url, str(rel_next.get("href")).strip())

    candidates = soup.find_all("a", href=True)
    page_match = re.search(r"([?&]page=)(\d+)", current_url)
    current_page = int(page_match.group(2)) if page_match else None

    for node in candidates:
        text = node.get_text(" ", strip=True).lower()
        href = str(node.get("href", "")).strip()
        if not href:
            continue
        if text in {"next", "далее", "вперед"} or "›" in text or "→" in text:
            return urljoin(current_url, href)
        if current_page is not None:
            m = re.search(r"([?&]page=)(\d+)", href)
            if m and int(m.group(2)) == current_page + 1:
                return urljoin(current_url, href)
    return None


def extract_links_from_repeated_structure(
    soup: BeautifulSoup,
    base_url: str,
    source_url: str,
) -> list[str]:
    """Extract product URLs using DOM repeated-structure analysis.

    Finds elements whose structural signature (tag + CSS classes) appears
    >= REPEATED_STRUCTURE_MIN_COUNT times on the page. These are assumed to
    be product cards in a listing grid. All <a href> inside them are returned
    as candidate product URLs.

    This algorithm is fully language-agnostic: it does not inspect URL path
    segments, link text, or any human-readable content.
    """
    from collections import defaultdict

    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc

    signature_elements: dict[tuple, list] = defaultdict(list)
    for element in soup.find_all(True):
        sig = _compute_element_signature(element)
        if sig[0] and sig[1]:
            signature_elements[sig].append(element)

    repeated_signatures = {
        sig: elements
        for sig, elements in signature_elements.items()
        if len(elements) >= REPEATED_STRUCTURE_MIN_COUNT
    }
    if not repeated_signatures:
        return []

    primary_sig = max(repeated_signatures, key=lambda s: len(repeated_signatures[s]))
    card_elements = repeated_signatures[primary_sig]

    seen: set[str] = set()
    results: list[str] = []

    for card in card_elements:
        for link_tag in card.find_all("a", href=True):
            href = link_tag.get("href", "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            if parsed.netloc != base_domain:
                continue
            path_lower = parsed.path.lower()
            if any(
                path_lower.startswith(prefix)
                for prefix in (
                    "/cart",
                    "/checkout",
                    "/login",
                    "/auth",
                    "/account",
                    "/wishlist",
                    "/compare",
                    "/sitemap",
                    "/robots",
                )
            ):
                continue
            clean_url = parsed._replace(fragment="", query="").geturl()
            if clean_url not in seen and clean_url != base_url and clean_url != source_url:
                seen.add(clean_url)
                results.append(clean_url)

    filtered: list[str] = []
    for url in results:
        parsed = urlparse(url)
        path = parsed.path
        if _is_excluded_link(url):
            continue
        if _is_category_url(path):
            continue
        if not _looks_like_product_url(path):
            continue
        path_lower = path.lower()
        if "/list/" in path_lower:
            continue
        if "/category/" in path_lower and not re.search(r"/\d{4,}", path_lower):
            continue
        if "/catalog/" in path_lower and not re.search(r"/\d{4,}", path_lower):
            continue
        if "/search" in path_lower:
            continue
        if path_lower.endswith("/") and path_lower.count("/") <= 3:
            continue
        filtered.append(url)
    return filtered


def extract_internal_links_all(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Extract all internal links from a page, deduplicated.

    Language-agnostic. Used for hub-page navigation traversal.
    Does not filter by URL pattern - returns all internal hrefs.
    The caller is responsible for further filtering.
    """
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc

    seen: set[str] = set()
    results: list[str] = []

    for tag in soup.find_all("a", href=True):
        href = tag.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.netloc != base_domain:
            continue
        path = parsed.path
        if not path or path == "/":
            continue
        clean_url = parsed._replace(fragment="", query="").geturl()
        if clean_url not in seen:
            seen.add(clean_url)
            results.append(clean_url)
    return results


def parse_sitemap_xml(xml_content: str, base_url: str) -> dict[str, list[str]]:
    """Parse a sitemap XML document.

    Returns a dict with two keys:
    - 'urls': list of <loc> URLs (product URLs in a regular sitemap)
    - 'sitemaps': list of nested sitemap URLs (in a sitemap index)

    Handles both sitemap index files and regular sitemaps.
    Language-agnostic: XML standard.
    """
    import xml.etree.ElementTree as ET

    _ = base_url
    result: dict[str, list[str]] = {"urls": [], "sitemaps": []}
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return result

    def _strip_ns(tag: str) -> str:
        return tag.split("}")[-1] if "}" in tag else tag

    tag_name = _strip_ns(root.tag)
    if tag_name == "sitemapindex":
        for sitemap_el in root:
            if _strip_ns(sitemap_el.tag) == "sitemap":
                for child in sitemap_el:
                    if _strip_ns(child.tag) == "loc" and child.text:
                        result["sitemaps"].append(child.text.strip())
    else:
        for url_el in root:
            if _strip_ns(url_el.tag) == "url":
                for child in url_el:
                    if _strip_ns(child.tag) == "loc" and child.text:
                        result["urls"].append(child.text.strip())
    return result
