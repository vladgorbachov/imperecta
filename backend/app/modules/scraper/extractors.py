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

logger = logging.getLogger(__name__)

_CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₴": "UAH",
    "₽": "RUB",
    "zł": "PLN",
    "lei": "RON",
}

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
)

_PRODUCT_LINK_HINTS = ("/product/", "/products/", "/item/", "/p/", "/tovar/", "/dp/")


@dataclass
class ExtractedProduct:
    """Unified extraction result."""

    title: str | None = None
    price: float | None = None
    original_price: float | None = None
    currency: str | None = None
    image_url: str | None = None
    description: str | None = None

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


def extract_from_jsonld(soup: BeautifulSoup) -> ExtractedProduct:
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
                if "price" in offers:
                    price = parse_price_text(str(offers.get("price")))
                elif "lowPrice" in offers:
                    price = parse_price_text(str(offers.get("lowPrice")))
                    if "highPrice" in offers:
                        original_price = parse_price_text(str(offers.get("highPrice")))
                elif "highPrice" in offers:
                    price = parse_price_text(str(offers.get("highPrice")))

                image = product.get("image")
                if isinstance(image, list):
                    image = image[0] if image else None
                elif isinstance(image, dict):
                    image = image.get("url")

                description = product.get("description")
                if isinstance(description, str) and len(description) > 2000:
                    description = description[:2000]

                currency = offers.get("priceCurrency") if isinstance(offers, dict) else None
                if isinstance(currency, str):
                    currency = currency.upper()

                return ExtractedProduct(
                    title=product.get("name"),
                    price=price,
                    original_price=original_price,
                    currency=currency,
                    image_url=image if isinstance(image, str) else None,
                    description=description if isinstance(description, str) else None,
                )
    return ExtractedProduct()


def extract_from_meta_tags(soup: BeautifulSoup) -> ExtractedProduct:
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
        result.price = parse_price_text(node["content"])
        if result.price is None:
            continue
        if currency_prop:
            cur = soup.find("meta", property=currency_prop) or soup.find(
                "meta",
                attrs={"name": currency_prop},
            )
            if cur and cur.get("content"):
                result.currency = str(cur.get("content")).upper()
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

    return result


def extract_with_custom_selectors(soup: BeautifulSoup, selectors: dict) -> ExtractedProduct:
    """
    Level 3 (optional): Custom CSS selectors from admin_marketplaces table.
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
            result.price = parse_price_text(element.get_text(strip=True))

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

    return result


def _detect_currency(text: str) -> str | None:
    lowered = text.lower()
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in lowered:
            return code
    if " usd" in lowered:
        return "USD"
    if " eur" in lowered:
        return "EUR"
    if " uah" in lowered:
        return "UAH"
    if " rub" in lowered:
        return "RUB"
    if " pln" in lowered:
        return "PLN"
    if " ron" in lowered:
        return "RON"
    return None


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
        result.price = parse_price_text(best)
        result.currency = _detect_currency(best)

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

    return result


def parse_price_text(text: str) -> float | None:
    """Parse price from text like '1 299,50 ₴', '$49.99', '1.299,50 €'."""
    if not text:
        return None

    cleaned = str(text).strip()
    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = re.sub(r"[^\d,.\-]", "", cleaned)
    match = re.search(r"(\d[\d.,]*\d|\d+)", cleaned)
    if not match:
        return None
    value = match.group(1)

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        parts = value.split(",")
        if len(parts[-1]) in (1, 2):
            value = value.replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "." in value:
        parts = value.split(".")
        if len(parts) > 1 and len(parts[-1]) == 3:
            value = value.replace(".", "")

    try:
        number = float(value)
        return number if number > 0 else None
    except ValueError:
        return None


def merge_results(*results: ExtractedProduct) -> ExtractedProduct:
    """Merge multiple extraction results. First non-None value wins."""
    merged = ExtractedProduct()
    for field_name in ["title", "price", "original_price", "currency", "image_url", "description"]:
        for result in results:
            value = getattr(result, field_name, None)
            if value is not None:
                setattr(merged, field_name, value)
                break
    return merged


def _looks_like_product_url(path: str) -> bool:
    lowered = path.lower()
    if any(hint in lowered for hint in _PRODUCT_LINK_HINTS):
        return True
    return bool(re.search(r"/\d{4,}", lowered))


def _is_excluded_link(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in _EXCLUDED_LINK_HINTS)


def extract_product_links(
    soup: BeautifulSoup,
    base_url: str,
    custom_selector: str | None = None,
) -> list[str]:
    """Extract product URLs from category/listing page."""
    links = []
    if custom_selector:
        links = soup.select(custom_selector)
    else:
        links = soup.find_all("a", href=True)

    parsed_base = urlparse(base_url)
    output: list[str] = []
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
        if not _looks_like_product_url(parsed.path):
            continue
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


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
