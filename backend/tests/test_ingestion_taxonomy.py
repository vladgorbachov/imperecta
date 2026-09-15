"""Taxonomy extraction + gated upsert payload completeness (no DB)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

from bs4 import BeautifulSoup

from app.modules.ingestion.taxonomy import (
    _normalize_taxonomy_name,
    _slugify,
    ensure_brand,
    ensure_category_chain,
)
from app.modules.scraper.extractors import (
    ExtractedProduct,
    extract_from_jsonld,
    extract_from_microdata,
    merge_results,
)

PAGE_URL = "https://shop.example/products/scrub-lollipop"

JSONLD_PRODUCT_WITH_BRAND_OBJECT = """
<html><head><script type="application/ld+json">
{"@type": "Product", "name": "Scrub Lollipop",
 "brand": {"@type": "Brand", "name": "Organic Shop"},
 "offers": {"price": "9.89", "priceCurrency": "EUR"}}
</script></head><body></body></html>
"""

JSONLD_PRODUCT_WITH_CATEGORY_STRING = """
<html><head><script type="application/ld+json">
{"@type": "Product", "name": "Scrub Lollipop", "brand": "Organic Shop",
 "category": "Beauty > Body Care > Scrubs",
 "offers": {"price": "9.89", "priceCurrency": "EUR"}}
</script></head><body></body></html>
"""

JSONLD_PRODUCT_WITH_BREADCRUMBS = """
<html><head>
<script type="application/ld+json">
{"@type": "Product", "name": "Scrub Lollipop",
 "offers": {"price": "9.89", "priceCurrency": "EUR"}}
</script>
<script type="application/ld+json">
{"@type": "BreadcrumbList", "itemListElement": [
  {"@type": "ListItem", "position": 1, "name": "Home",
   "item": "https://shop.example/"},
  {"@type": "ListItem", "position": 2, "name": "Body Care",
   "item": "https://shop.example/body-care"},
  {"@type": "ListItem", "position": 3, "name": "Scrubs",
   "item": "https://shop.example/body-care/scrubs"},
  {"@type": "ListItem", "position": 4, "name": "Scrub Lollipop",
   "item": "https://shop.example/products/scrub-lollipop"}
]}
</script>
</head><body></body></html>
"""

MICRODATA_PRODUCT_WITH_BRAND = """
<html><body>
<div itemscope itemtype="http://schema.org/Product">
  <span itemprop="name">Scrub Lollipop</span>
  <div itemprop="brand" itemscope itemtype="http://schema.org/Brand">
    <meta itemprop="name" content="Organic Shop">
  </div>
  <div itemprop="offers" itemscope itemtype="http://schema.org/Offer">
    <span itemprop="price">9.89</span>
    <meta itemprop="priceCurrency" content="EUR">
  </div>
</div>
</body></html>
"""


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def test_jsonld_brand_object_extracted() -> None:
    ep = extract_from_jsonld(_soup(JSONLD_PRODUCT_WITH_BRAND_OBJECT), PAGE_URL)
    assert ep.brand == "Organic Shop"
    assert ep.category_path is None


def test_jsonld_category_string_split_into_path() -> None:
    ep = extract_from_jsonld(_soup(JSONLD_PRODUCT_WITH_CATEGORY_STRING), PAGE_URL)
    assert ep.brand == "Organic Shop"
    assert ep.category_path == ["Beauty", "Body Care", "Scrubs"]


def test_jsonld_breadcrumbs_drop_root_and_product_crumbs() -> None:
    ep = extract_from_jsonld(_soup(JSONLD_PRODUCT_WITH_BREADCRUMBS), PAGE_URL)
    assert ep.category_path == ["Body Care", "Scrubs"]


def test_microdata_brand_nested_scope() -> None:
    ep = extract_from_microdata(_soup(MICRODATA_PRODUCT_WITH_BRAND), PAGE_URL)
    assert ep.brand == "Organic Shop"


def test_merge_results_carries_taxonomy_fields() -> None:
    a = ExtractedProduct(title="X")
    b = ExtractedProduct(brand="Organic Shop", category_path=["Body Care"])
    merged = merge_results(a, b)
    assert merged.brand == "Organic Shop"
    assert merged.category_path == ["Body Care"]


def test_slugify_and_normalize() -> None:
    assert _slugify("Body Care > Scrubs") == "body-care-scrubs"
    assert _slugify("  Крем для рук  ") == "крем-для-рук"
    assert _normalize_taxonomy_name("  Organic   SHOP ") == "organic shop"


def _db_returning(value):
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = value
    return db


def test_ensure_brand_insert_payload_covers_not_null_columns() -> None:
    db = _db_returning(None)
    captured: dict = {}

    def fake_gate_insert(_db, *, table, fields, reject_source):
        captured["table"] = table
        captured["fields"] = fields
        return True

    with patch("app.modules.ingestion.taxonomy._gate_insert", fake_gate_insert):
        brand_id = ensure_brand(db, "Organic Shop")

    assert isinstance(brand_id, UUID)
    assert captured["table"] == "dim_brand"
    assert set(captured["fields"]) == {"id", "name", "slug", "name_normalized", "is_active"}
    assert captured["fields"]["is_active"] is True


def test_ensure_category_chain_inserts_every_level_with_not_null_columns() -> None:
    db = _db_returning(None)
    inserts: list[dict] = []

    def fake_gate_insert(_db, *, table, fields, reject_source):
        inserts.append({"table": table, **fields})
        return True

    with patch("app.modules.ingestion.taxonomy._gate_insert", fake_gate_insert):
        leaf = ensure_category_chain(db, ["Beauty", "Body Care"])

    assert isinstance(leaf, UUID)
    assert [i["level"] for i in inserts] == [1, 2]
    assert inserts[0]["parent_id"] is None
    assert inserts[1]["parent_id"] == inserts[0]["id"]
    assert inserts[1]["path"] == "Beauty > Body Care"
    for row in inserts:
        assert row["is_active"] is True
        assert row["product_count"] == 0
        assert row["slug"]


def test_ensure_brand_race_falls_back_to_reselect() -> None:
    existing_id = UUID("00000000-0000-0000-0000-00000000beef")
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.side_effect = [None, existing_id]

    with patch("app.modules.ingestion.taxonomy._gate_insert", return_value=False):
        assert ensure_brand(db, "Organic Shop") == existing_id
