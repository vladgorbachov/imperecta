"""GTIN capture + matching method priority (gtin > brand_model > title_exact).

Pure logic; the Rust jsonld twin carries the same gtin cases in its unit
tests (rust_core/src/jsonld.rs gtin_tests).
"""

from __future__ import annotations

import uuid

from bs4 import BeautifulSoup

from app.modules.matching.engine import (
    CONFIDENCE_GTIN,
    CONFIDENCE_TITLE_EXACT,
    METHOD_BRAND_MODEL,
    METHOD_GTIN,
    METHOD_TITLE_EXACT,
    METHOD_UNMATCHED,
    build_match_fields,
    gtin_group_id,
    title_group_id,
)
from app.modules.matching.signature import extract_match_signature
from app.modules.scraper.extractors import extract_from_jsonld

BRANDS = frozenset({"sencor"})


def _soup(jsonld: str) -> BeautifulSoup:
    return BeautifulSoup(
        f'<html><head><script type="application/ld+json">{jsonld}</script></head></html>',
        "html.parser",
    )


def test_jsonld_gtin13_preferred_and_separators_stripped() -> None:
    ep = extract_from_jsonld(
        _soup(
            '{"@type":"Product","name":"Widget","gtin13":"590-1234 123457",'
            '"gtin8":"12345670","offers":{"price":"9.99","priceCurrency":"EUR"}}'
        )
    )
    assert ep.gtin == "5901234123457"


def test_jsonld_invalid_gtin_rejected_mpn_kept() -> None:
    ep = extract_from_jsonld(
        _soup(
            '{"@type":"Product","name":"Widget","gtin":"not-a-number",'
            '"mpn":"BQ2942W","offers":{"price":"9.99","priceCurrency":"EUR"}}'
        )
    )
    assert ep.gtin is None
    assert ep.mpn == "BQ2942W"


def test_jsonld_numeric_gtin_value_accepted() -> None:
    ep = extract_from_jsonld(
        _soup(
            '{"@type":"Product","name":"Widget","gtin":4006381333931,'
            '"offers":{"price":"9.99","priceCurrency":"EUR"}}'
        )
    )
    assert ep.gtin == "4006381333931"


def test_gtin_beats_brand_model() -> None:
    product_id = str(uuid.uuid4())
    signature = extract_match_signature("sencor sfd 950ss", BRANDS)
    fields = build_match_fields(
        product_id, signature, sku_universal="4006381333931"
    )
    assert fields["match_method"] == METHOD_GTIN
    assert fields["match_confidence"] == CONFIDENCE_GTIN
    assert fields["match_group_id"] == str(gtin_group_id("4006381333931"))


def test_brand_model_beats_title_exact() -> None:
    product_id = str(uuid.uuid4())
    signature = extract_match_signature("sencor sfd 950ss", BRANDS)
    fields = build_match_fields(
        product_id, signature, title_en="Sencor Blender", product_type_en="Blender"
    )
    assert fields["match_method"] == METHOD_BRAND_MODEL


def test_title_exact_when_no_signature() -> None:
    product_id = str(uuid.uuid4())
    fields = build_match_fields(
        product_id,
        None,
        title_en="Green plastic ashtray",
        product_type_en="Ashtray",
    )
    assert fields["match_method"] == METHOD_TITLE_EXACT
    assert fields["match_confidence"] == CONFIDENCE_TITLE_EXACT
    assert fields["match_group_id"] == str(
        title_group_id("Green plastic ashtray", "Ashtray")
    )


def test_title_group_normalizes_case_and_spaces() -> None:
    a = title_group_id("Green  Plastic Ashtray", "Ashtray")
    b = title_group_id("green plastic ashtray", "ashtray")
    assert a == b
    assert a != title_group_id("green plastic ashtray", "Bowl")


def test_unmatched_without_any_identity() -> None:
    fields = build_match_fields(str(uuid.uuid4()), None)
    assert fields == {"id": fields["id"], "match_method": METHOD_UNMATCHED}


def test_gtin_and_brandmodel_group_id_spaces_disjoint() -> None:
    # "gtin:" keys use ':' which cannot occur in "brand|code" keys.
    from app.modules.matching.signature import match_group_id

    assert gtin_group_id("12345670") != match_group_id("gtin", "12345670")
