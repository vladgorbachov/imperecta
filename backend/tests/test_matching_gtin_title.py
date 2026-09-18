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


# --- M2b: title normalization + similarity + merge determinism --------------

from app.modules.matching.engine import (  # noqa: E402
    CONFIDENCE_TITLE_SIM,
    METHOD_TITLE_SIM,
    TITLE_SIM_THRESHOLD,
)
from app.modules.matching.signature import (  # noqa: E402
    normalize_title_tokens,
    title_similarity,
)


def test_title_normalization_glues_units_drops_stopwords_sorts() -> None:
    assert normalize_title_tokens("Sencor Electric Kettle 1.7 l, White") == [
        "1.7l",
        "electric",
        "kettle",
        "sencor",
        "white",
    ]
    assert normalize_title_tokens("Kettle with the Lid") == ["kettle", "lid"]
    assert normalize_title_tokens("1.7L kettle") == normalize_title_tokens(
        "Kettle 1.7 l"
    )


def test_title_key_v2_ignores_word_order_and_glue_words() -> None:
    a = title_group_id("Sencor Kettle 1.7 l White", "Kettle")
    b = title_group_id("White 1.7l Kettle Sencor", "Kettle")
    assert a == b


def test_title_similarity_near_identical_high() -> None:
    a = normalize_title_tokens("Sencor Electric Kettle 1.7 l White")
    b = normalize_title_tokens("Sencor Kettle 1.7l white")
    assert title_similarity(a, b) >= TITLE_SIM_THRESHOLD


def test_title_similarity_unit_conflict_forces_zero() -> None:
    a = normalize_title_tokens("Samsung Galaxy S24 256gb Black")
    b = normalize_title_tokens("Samsung Galaxy S24 512gb Black")
    assert title_similarity(a, b) == 0.0


def test_title_similarity_unrelated_low() -> None:
    a = normalize_title_tokens("Green plastic ashtray")
    b = normalize_title_tokens("Sencor kettle 1.7l")
    assert title_similarity(a, b) < 0.2


def test_title_sim_constants_sane() -> None:
    assert METHOD_TITLE_SIM == "title_sim"
    assert 0 < CONFIDENCE_TITLE_SIM < CONFIDENCE_GTIN


def test_title_facades_parity_when_built() -> None:
    import pytest as _pytest

    rust = _pytest.importorskip("imperecta_core")
    if not hasattr(rust, "normalize_title_tokens"):
        _pytest.skip("imperecta_core built without title support")
    cases = [
        "Sencor Electric Kettle 1.7 l, White",
        "Kettle with the Lid",
        "Samsung Galaxy S24 256gb Black",
        "Green plastic ashtray",
        "White 1.7l Kettle Sencor",
    ]
    for title in cases:
        assert list(rust.normalize_title_tokens(title)) == normalize_title_tokens(
            title
        ), title
    for ta in cases:
        for tb in cases:
            a_py = normalize_title_tokens(ta)
            b_py = normalize_title_tokens(tb)
            assert abs(
                rust.title_similarity(a_py, b_py) - title_similarity(a_py, b_py)
            ) < 1e-9
