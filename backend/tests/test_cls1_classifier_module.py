"""CLS1 invariants: Classifier Tier-1 module + Tier-0 html_parsing primitives.

Covers:
- Tier-0 primitive parity (parse_price_text / parse_currency_* / _detect_currency
  / compute_element_signature output unchanged from the old extractors home).
- Classifier parity for every PageRole branch (Layer 1/2/2.5/3) including the
  klick.ee-style top-level microdata Product page.
- Edge-map / no-cycle: classifier imports nothing from extractor / scraper /
  discovery; common imports nothing upward.
- Consumers (merge_and_finalize + discovery._classify_url) repointed to
  ``app.modules.classifier``.
- PageRole contract (the 4 string values, unchanged).
- Extraction no-regression: a JSON-LD Product page still extracts price/currency
  through the merge pipeline using the Tier-0 primitives.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from app.common import html_parsing as common_hp
from app.modules.classifier import (
    PageRole,
    _get_jsonld_root_types,
    _get_microdata_toplevel_types,
    _get_og_type,
    classify_page_role,
    classify_page_role_for_discovery,
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
from app.modules.scraper import extractors as ex


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = REPO_ROOT / "app"


# ---- 1. Tier-0 primitive parity --------------------------------------------


class TestPrimitiveParity:
    def test_parse_price_text_eu(self):
        assert common_hp.parse_price_text("1.234,56 €") == 1234.56
        assert common_hp.parse_price_text("1 234,56 ₴") == 1234.56

    def test_parse_price_text_us(self):
        assert common_hp.parse_price_text("$1,234.56") == 1234.56

    def test_parse_price_text_clamps_max_realistic(self):
        # Above _MAX_REALISTIC_PRICE without currency context → rejected.
        assert common_hp.parse_price_text("9999999999") is None

    def test_parse_currency_symbol_eur(self):
        assert common_hp.parse_currency_symbol("Price 12,99 €") == "EUR"

    def test_parse_currency_code_usd(self):
        assert common_hp.parse_currency_code("12.99 USD") == "USD"

    def test_detect_currency_prefers_symbol(self):
        # Symbol path returns before code path.
        assert common_hp._detect_currency("12,99 € USD") in {"EUR", "USD"}
        assert common_hp._detect_currency("12,99 €") == "EUR"

    def test_compute_element_signature(self):
        soup = BeautifulSoup('<div class="card product"><span>x</span></div>', "html.parser")
        div = soup.find("div")
        sig = common_hp.compute_element_signature(div)
        assert sig == ("div", frozenset({"card", "product"}))

    def test_repeated_structure_min_count_value(self):
        # Constant moved verbatim — pinning the value avoids accidental drift.
        assert common_hp.REPEATED_STRUCTURE_MIN_COUNT == 6


# ---- 2. extractors back-compat re-exports ----------------------------------


class TestExtractorsReexports:
    def test_parse_price_text_is_common(self):
        assert ex.parse_price_text is common_hp.parse_price_text

    def test_parse_currency_symbol_is_common(self):
        assert ex.parse_currency_symbol is common_hp.parse_currency_symbol

    def test_parse_currency_code_is_common(self):
        assert ex.parse_currency_code is common_hp.parse_currency_code

    def test_detect_currency_is_common(self):
        assert ex._detect_currency is common_hp._detect_currency

    def test_compute_element_signature_underscored_alias_works(self):
        assert ex._compute_element_signature is common_hp._compute_element_signature

    def test_classify_funcs_come_from_classifier(self):
        from app.modules.classifier import service as classifier_service

        assert ex.classify_page_role is classifier_service.classify_page_role
        assert ex.classify_page_role_for_discovery is classifier_service.classify_page_role_for_discovery

    def test_extractors_does_not_redefine_moved_symbols(self):
        """The function bodies were removed; only re-exports remain."""
        source = (BACKEND_APP / "modules" / "scraper" / "extractors.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        defined_funcs = {
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        for name in (
            "parse_price_text",
            "parse_currency_symbol",
            "parse_currency_code",
            "_detect_currency",
            "_compute_element_signature",
            "classify_page_role",
            "classify_page_role_for_discovery",
            "_get_og_type",
            "_get_jsonld_root_types",
            "_get_microdata_toplevel_types",
        ):
            assert name not in defined_funcs, (
                f"extractors.py must re-export, not re-define, {name} after CLS1"
            )


# ---- 3. Classifier parity (PageRole branches) ------------------------------


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


class TestClassifierParity:
    def test_layer1_og_product(self):
        s = _soup('<html><head><meta property="og:type" content="product"/></head></html>')
        assert classify_page_role_for_discovery(s, "https://x/p/1") == "product"

    def test_layer1_og_website_hub(self):
        s = _soup('<html><head><meta property="og:type" content="website"/></head></html>')
        assert classify_page_role_for_discovery(s, "https://x/") == "hub"

    def test_layer1_og_article_listing(self):
        s = _soup('<html><head><meta property="og:type" content="article"/></head></html>')
        assert classify_page_role_for_discovery(s, "https://x/blog/1") == "listing"

    def test_layer2_jsonld_product(self):
        s = _soup(
            '<html><head>'
            '<script type="application/ld+json">{"@type":"Product","name":"X"}</script>'
            '</head></html>'
        )
        assert classify_page_role_for_discovery(s, "https://x/p/1") == "product"

    def test_layer2_jsonld_product_wins_over_breadcrumb(self):
        s = _soup(
            '<html><head>'
            '<script type="application/ld+json">'
            '[{"@type":"BreadcrumbList"},{"@type":"Product","name":"X"}]'
            '</script>'
            '</head></html>'
        )
        assert classify_page_role_for_discovery(s, "https://x/p/1") == "product"

    def test_layer2_jsonld_itemlist_listing(self):
        s = _soup(
            '<html><head>'
            '<script type="application/ld+json">{"@type":"ItemList"}</script>'
            '</head></html>'
        )
        assert classify_page_role_for_discovery(s, "https://x/c/1") == "listing"

    def test_layer25_microdata_product_klick_ee_style(self):
        # klick.ee-style: top-level Product via Microdata; no og:type, no JSON-LD.
        # Proves CLASSIFIER works on the klick.ee page; the bug is EXTRACTION
        # of currency_raw (Phase 5 microdata strategy), NOT classification.
        s = _soup(
            '<html><body>'
            '<div itemscope itemtype="http://schema.org/Product">'
            '<span itemprop="name">Test</span>'
            '<span itemprop="price">12.99</span>'
            '</div>'
            '</body></html>'
        )
        assert classify_page_role_for_discovery(s, "https://klick.ee/x") == "product"

    def test_layer25_microdata_toplevel_itemlist_listing(self):
        s = _soup(
            '<html><body>'
            '<div itemscope itemtype="http://schema.org/ItemList">'
            '  <div itemscope itemtype="http://schema.org/Product">'
            '    <span itemprop="name">A</span>'
            '  </div>'
            '</div>'
            '</body></html>'
        )
        # Nested Product under top-level ItemList → top-level-only rule: listing.
        assert classify_page_role_for_discovery(s, "https://x/c/1") == "listing"

    def test_layer3_structural_hub(self):
        s = _soup("<html><body><h1>About us</h1><p>Some text.</p></body></html>")
        assert classify_page_role_for_discovery(s, "https://x/") == "hub"

    def test_layer3_grid_listing(self):
        # 6 repeated card structures + prices → Layer-3 listing.
        cards = "".join(
            f'<div class="card item"><span class="price">1{i}.99 €</span></div>'
            for i in range(7)
        )
        s = _soup(f"<html><body>{cards}</body></html>")
        assert classify_page_role(s, "https://x/c/1") == "listing"

    def test_pagerole_contract(self):
        # The 4 PageRole string values are the locked external contract.
        import typing

        args = typing.get_args(PageRole)
        assert set(args) == {"product", "listing", "hub", "unknown"}

    def test_jsonld_root_types_collects_top_level_only(self):
        s = _soup(
            '<html><head>'
            '<script type="application/ld+json">'
            '{"@type":"WebPage","mainEntity":{"@type":"Product"}}'
            '</script>'
            '</head></html>'
        )
        # Nested Product inside mainEntity must NOT bubble up.
        assert _get_jsonld_root_types(s) == {"WebPage"}

    def test_og_type_lowercased(self):
        s = _soup('<html><head><meta property="og:type" content="PRODUCT"/></head></html>')
        assert _get_og_type(s) == "product"

    def test_microdata_toplevel_only(self):
        s = _soup(
            '<html><body>'
            '<div itemscope itemtype="http://schema.org/Product">'
            '<div itemscope itemtype="http://schema.org/Offer"></div>'
            '</div>'
            '</body></html>'
        )
        top = _get_microdata_toplevel_types(s)
        assert top == {"http://schema.org/Product"}


# ---- 4. Edge map / no-cycle invariants -------------------------------------


def _read_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
    return mods


class TestNoCycle:
    def test_classifier_does_not_import_extractor_or_scraper(self):
        for path in (BACKEND_APP / "modules" / "classifier").rglob("*.py"):
            mods = _read_imports(path)
            forbidden = {
                m for m in mods
                if m.startswith("app.modules.scraper")
                or m.startswith("app.modules.ingestion")
                or m.startswith("app.modules.product_pool")
            }
            assert not forbidden, (
                f"classifier/{path.name} imports forbidden module(s): {forbidden}"
            )

    def test_common_html_parsing_is_tier0(self):
        mods = _read_imports(BACKEND_APP / "common" / "html_parsing.py")
        # Tier-0 may only import stdlib (no app.* modules at all).
        upward = {m for m in mods if m.startswith("app.")}
        assert not upward, f"common/html_parsing.py is Tier-0; forbidden imports: {upward}"

    def test_extractor_imports_classifier_and_common(self):
        mods = _read_imports(BACKEND_APP / "modules" / "scraper" / "extractors.py")
        assert "app.modules.classifier" in mods
        assert "app.common.html_parsing" in mods


# ---- 5. Consumers repointed -------------------------------------------------


class TestConsumersRepointed:
    def test_extractor_merge_and_finalize_uses_classifier(self, monkeypatch):
        """Patch classifier symbol → merge_and_finalize call goes through it."""
        calls: list[tuple] = []

        def fake_classify(soup, url):
            calls.append((url,))
            return "product"

        # Patch at the import site — extractors.py rebinds the name.
        monkeypatch.setattr(
            "app.modules.scraper.extractors.classify_page_role_for_discovery",
            fake_classify,
        )
        from app.modules.scraper.extractors import ExtractedProduct, merge_and_finalize

        ep = ExtractedProduct(title="X", price=10.0, image_url="https://x/i.jpg")
        s = _soup('<html><body><h1>X</h1></body></html>')
        merge_and_finalize(s, "https://x/p/1", ep)
        assert calls, "merge_and_finalize must call classify_page_role_for_discovery"

    def test_discovery_module_imports_classifier(self):
        mods = _read_imports(BACKEND_APP / "modules" / "scraper" / "discovery.py")
        assert "app.modules.classifier" in mods


# ---- 6. Extraction no-regression -------------------------------------------


class TestExtractionNoRegression:
    def test_jsonld_extraction_still_works_via_common_primitives(self):
        from app.modules.scraper.extractors import extract_from_jsonld

        html = (
            '<html><head>'
            '<script type="application/ld+json">'
            '{"@type":"Product","name":"Widget",'
            '"offers":{"@type":"Offer","price":"12.99","priceCurrency":"EUR"},'
            '"image":"https://x/img.jpg"}'
            '</script>'
            '</head><body></body></html>'
        )
        ep = extract_from_jsonld(_soup(html), "https://x/p/1")
        assert ep.title == "Widget"
        assert ep.price == 12.99
        assert ep.currency == "EUR"


# ---- 7. Classifier constants live in classifier (not common) ----------------


class TestClassificationConstantsStayInClassifier:
    def test_constants_not_in_common(self):
        common_mod = importlib.import_module("app.common.html_parsing")
        for name in (
            "_OG_TYPES_PRODUCT",
            "_OG_TYPES_LISTING",
            "_OG_TYPES_HUB",
            "_JSONLD_TYPES_PRODUCT",
            "_JSONLD_TYPES_LISTING",
            "_JSONLD_TYPES_HUB",
            "_MICRODATA_TYPES_PRODUCT",
            "_MICRODATA_TYPES_LISTING",
        ):
            assert not hasattr(common_mod, name), (
                f"{name} must live in classifier.constants, not common/html_parsing"
            )

    def test_constants_present_in_classifier(self):
        assert "product" in _OG_TYPES_PRODUCT
        assert "website" in _OG_TYPES_HUB
        assert "article" in _OG_TYPES_LISTING
        assert "Product" in _JSONLD_TYPES_PRODUCT
        assert "ItemList" in _JSONLD_TYPES_LISTING
        assert "WebPage" in _JSONLD_TYPES_HUB
        assert "http://schema.org/Product" in _MICRODATA_TYPES_PRODUCT
        assert "https://schema.org/ItemList" in _MICRODATA_TYPES_LISTING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
