"""Legacy layer string -> neutral BackendId mapping (Stage 1b boundary)."""

from __future__ import annotations

import pytest

from app.modules.scraper.fetch_backends import (
    ALL_LEGACY_LAYER_STRINGS,
    LEGACY_LAYER_TO_BACKEND,
    BackendId,
    backend_id_persisted,
    legacy_layer_to_backend_id,
)


@pytest.mark.parametrize(
    "legacy,expected",
    [
        ("httpx", BackendId.DIRECT_HTTP),
        ("decodo", BackendId.PROXY_PROVIDER),
        ("decodo_static", BackendId.PROXY_PROVIDER),
        ("playwright", BackendId.BROWSER_RENDER),
    ],
)
def test_legacy_layer_maps_to_single_backend_id(legacy: str, expected: BackendId) -> None:
    assert legacy_layer_to_backend_id(legacy) is expected
    assert LEGACY_LAYER_TO_BACKEND[legacy] is expected
    assert backend_id_persisted(expected) in {
        "direct_http",
        "proxy_provider",
        "browser_render",
    }


def test_legacy_mapping_is_total() -> None:
    assert set(LEGACY_LAYER_TO_BACKEND.keys()) == ALL_LEGACY_LAYER_STRINGS
    assert len(LEGACY_LAYER_TO_BACKEND) == len(ALL_LEGACY_LAYER_STRINGS)


def test_persisted_values_are_neutral_vendor_free() -> None:
    for backend_id in BackendId:
        persisted = backend_id_persisted(backend_id)
        assert persisted is not None
        assert "decodo" not in persisted
        assert "httpx" not in persisted
        assert "playwright" not in persisted
