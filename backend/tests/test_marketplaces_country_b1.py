"""Zone B1: explicit marketplace country on create/edit (no TLD fallback)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.modules.marketplaces import service as marketplaces_service
from app.modules.marketplaces.service import MarketplaceService


def test_tld_inference_helpers_removed() -> None:
    """Create path must not expose TLD guess or arbitrary fallback helpers."""
    assert not hasattr(MarketplaceService, "_tld_to_country")
    assert not hasattr(MarketplaceService, "_fallback_country_code")
    assert not hasattr(MarketplaceService, "_resolve_country_and_currency")

    source = Path(marketplaces_service.__file__).read_text(encoding="utf-8")
    assert "_fallback_country_code" not in source
    assert "_resolve_country_and_currency" not in source
    assert "_tld_to_country" not in source


@pytest.mark.asyncio
async def test_resolve_explicit_country_rejects_unknown() -> None:
    svc = MarketplaceService.__new__(MarketplaceService)
    svc._country_exists = AsyncMock(return_value=False)
    with pytest.raises(ValueError, match="Unknown country code: XX"):
        await svc._resolve_explicit_country("XX")


@pytest.mark.asyncio
async def test_resolve_explicit_country_accepts_world_for_com_domains() -> None:
    """Generic TLD domains must use the admin-chosen code (e.g. ZZ), not a guess."""
    svc = MarketplaceService.__new__(MarketplaceService)
    svc._country_exists = AsyncMock(return_value=True)
    svc._lookup_country_currency = AsyncMock(return_value="EUR")
    svc._currency_exists = AsyncMock(return_value=True)

    code, currency = await svc._resolve_explicit_country("zz")

    assert code == "ZZ"
    assert currency == "EUR"
    svc._country_exists.assert_awaited_once_with("ZZ")


@pytest.mark.asyncio
async def test_update_country_syncs_operates_in_and_currency() -> None:
    svc = MarketplaceService.__new__(MarketplaceService)
    svc._resolve_explicit_country = AsyncMock(return_value=("NL", "EUR"))

    class _FakeMarketplace:
        name = "Shop"
        is_active = True
        country_code = "KZ"

    mp = _FakeMarketplace()
    svc.db = AsyncMock()
    svc.db.get = AsyncMock(return_value=mp)
    svc.db.refresh = AsyncMock()

    captured: dict[str, object] = {}

    async def _fake_write_meta_async(**kwargs: object) -> object:
        captured.update(kwargs)
        return type("R", (), {"ok": True})()

    import app.modules.marketplaces.service as svc_mod

    original = svc_mod.write_meta_async
    svc_mod.write_meta_async = _fake_write_meta_async
    try:
        result = await svc.update_marketplace(
            __import__("uuid").uuid4(),
            {"country_code": "NL"},
        )
    finally:
        svc_mod.write_meta_async = original

    assert result is mp
    fields = captured["fields"]
    assert fields["country_code"] == "NL"
    assert fields["operates_in"] == ["NL"]
    assert fields["currency_code"] == "EUR"
