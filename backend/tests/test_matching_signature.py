"""Match-signature contract tests (pure logic; mirrors rust_core matching.rs).

Live-pool sourced examples: junk slug names, multilingual titles, unit
tokens. The Rust twin's unit tests pin the same cases — keep both in sync.
"""

from __future__ import annotations

import uuid

import pytest

from app.modules.matching.engine import (
    METHOD_BRAND_MODEL,
    METHOD_UNMATCHED,
    build_match_fields,
)
from app.modules.matching.signature import (
    CONFIDENCE_HEURISTIC_BRAND,
    CONFIDENCE_KNOWN_BRAND,
    extract_match_signature,
    match_group_id,
)

BRANDS = frozenset({"sencor", "samsung", "xiaomi", "a4tech"})


def test_junk_slug_names_are_unmatchable() -> None:
    assert extract_match_signature("pb00613262.html", BRANDS) is None
    assert extract_match_signature("9000863112", BRANDS) is None
    assert extract_match_signature("1180243", BRANDS) is None
    assert extract_match_signature("", BRANDS) is None
    assert extract_match_signature(None, BRANDS) is None


def test_model_code_with_known_brand() -> None:
    sig = extract_match_signature("sencor sfd 950ss", BRANDS)
    assert sig is not None
    assert sig["brand"] == "sencor"
    assert sig["code"] == "sfd950ss"
    assert sig["confidence"] == CONFIDENCE_KNOWN_BRAND


def test_heuristic_brand_and_unit_exclusion() -> None:
    # "492w" reads as wattage -> attr; shop-internal "d552211" is the code.
    sig = extract_match_signature("trust gxt 492w carus white d552211", BRANDS)
    assert sig is not None
    assert sig["brand"] == "trust"
    assert "492w" in sig["attrs"]
    assert "d552211" in sig["codes"]
    assert sig["confidence"] == CONFIDENCE_HEURISTIC_BRAND


def test_units_are_attrs_not_codes() -> None:
    sig = extract_match_signature("samsung galaxy s24 ultra 256gb", BRANDS)
    assert sig is not None
    assert sig["brand"] == "samsung"
    assert sig["code"] == "galaxys24"
    assert "256gb" in sig["attrs"]
    assert "256gb" not in sig["codes"]


def test_short_mixed_token_captured_via_join() -> None:
    sig = extract_match_signature("xiaomi oclean f1 dark blue", BRANDS)
    assert sig is not None
    assert sig["code"] == "ocleanf1"


def test_same_product_different_spacing_same_group() -> None:
    a = extract_match_signature("sencor sfd 950ss blender", BRANDS)
    b = extract_match_signature("blender sencor sfd950ss", BRANDS)
    assert a is not None and b is not None
    assert a["brand"] == b["brand"]
    assert a["code"] == b["code"]
    assert match_group_id(a["brand"], a["code"]) == match_group_id(
        b["brand"], b["code"]
    )


def test_style_number_is_weak_code() -> None:
    sig = extract_match_signature(
        "tricou under armour ua big logo ss 1109226", frozenset()
    )
    assert sig is not None
    assert "1109226" in sig["codes"]


def test_mixed_brand_token_never_becomes_the_code() -> None:
    """Incident: mixed alnum brands (a4tech) minted brand-wide mega-groups."""
    brands = frozenset({"a4tech"})
    sig = extract_match_signature("a4tech bloody r73 ultra duo", brands)
    assert sig is not None
    assert sig["brand"] == "a4tech"
    assert sig["code"] == "bloodyr73"
    assert "a4tech" not in sig["codes"]
    assert extract_match_signature("klaviatura a4tech kr 92", brands) is None


def test_no_code_means_unmatchable_even_with_brand() -> None:
    assert extract_match_signature("rohelisest plastikust tuhatoos", BRANDS) is None


def test_group_id_deterministic() -> None:
    assert match_group_id("sencor", "sfd950ss") == match_group_id(
        "sencor", "sfd950ss"
    )
    assert match_group_id("sencor", "sfd950ss") != match_group_id(
        "samsung", "sfd950ss"
    )


def test_build_match_fields_matched_and_unmatched() -> None:
    product_id = str(uuid.uuid4())
    sig = extract_match_signature("sencor sfd 950ss", BRANDS)
    fields = build_match_fields(product_id, sig)
    assert fields["match_method"] == METHOD_BRAND_MODEL
    assert fields["match_confidence"] == CONFIDENCE_KNOWN_BRAND
    assert uuid.UUID(fields["match_group_id"])

    unfields = build_match_fields(product_id, None)
    assert unfields == {"id": product_id, "match_method": METHOD_UNMATCHED}


def test_rust_parity_when_built() -> None:
    """Rust and Python implementations must agree on the shared cases."""
    rust = pytest.importorskip("imperecta_core")
    if not hasattr(rust, "extract_match_signature"):
        pytest.skip("imperecta_core built without matching support")
    cases = [
        "pb00613262.html",
        "9000863112",
        "sencor sfd 950ss",
        "trust gxt 492w carus white d552211",
        "samsung galaxy s24 ultra 256gb",
        "xiaomi oclean f1 dark blue",
        "blender sencor sfd950ss",
        "tricou under armour ua big logo ss 1109226",
        "rohelisest plastikust tuhatoos",
        "colmi smartring colmi r12 20mm 10 czarny.bhtml",
        "haier sxi1c3bf2bt 01 d542718",
        "a4tech bloody r73 ultra duo",
        "klaviatura a4tech kr 92",
    ]
    for name in cases:
        py = extract_match_signature(name, BRANDS)
        rs = rust.extract_match_signature(name, list(BRANDS))
        assert py == rs, f"parity mismatch for {name!r}: {py} != {rs}"
