"""Z-JSDETECT-OBSERVE: structural shell detector predicate.

Pure unit tests for the ``_would_escalate_shell`` predicate. The predicate is
called from scrape_product in observe-only mode (it logs but never mutates the
scrape result), so the contract worth pinning is the predicate itself: the
exact combination of scrape_tier, used_backend, extractor currency verdict, and
classifier page-role that would trigger an escalation under ENFORCE.

The observe block in scrape_product is side-effect-free by construction
(broad except + log only), so behavior parity with HEAD is provided by the
EMPTY A/B FAILED+SKIPPED diff at the suite level — no behavior test needed
here.
"""

from __future__ import annotations

import pytest

from app.modules.scraper.fetch_backends import BackendId
from app.modules.scraper.scraper_pool import _would_escalate_shell


@pytest.mark.parametrize(
    "scrape_tier,used_backend,merged_currency,role,expected",
    [
        # Both signals empty on a Tier-1 direct HTTP fetch → would escalate.
        (1, BackendId.DIRECT_HTTP, None, "unknown", True),
        # Listing role on a FactListing PDP URL is degraded (likely shell with
        # category-style markup) → also a legitimate escalation signal.
        (1, BackendId.DIRECT_HTTP, None, "listing", True),
        # Extractor found a currency → page rendered fine, no escalation.
        (1, BackendId.DIRECT_HTTP, "EUR", "unknown", False),
        # Classifier says product → real product signals present, no escalation.
        (1, BackendId.DIRECT_HTTP, None, "product", False),
        # Tier 2 already leads with a JS-capable backend; nothing to protect.
        (2, BackendId.DIRECT_HTTP, None, "unknown", False),
        # Already on a JS-capable backend; no further escalation target.
        (1, BackendId.PROXY_PROVIDER, None, "unknown", False),
        (1, BackendId.BROWSER_RENDER, None, "unknown", False),
        # No backend succeeded (None) — handled earlier in scrape_product;
        # predicate must not fire.
        (1, None, None, "unknown", False),
    ],
    ids=[
        "tier1-direct-http-shell",
        "tier1-direct-http-listing-role",
        "tier1-direct-http-currency-set",
        "tier1-direct-http-product-role",
        "tier2-blocked-by-tier-gate",
        "tier1-proxy-provider-not-direct-http",
        "tier1-browser-render-not-direct-http",
        "no-used-backend",
    ],
)
def test_would_escalate_shell_predicate(
    scrape_tier: int,
    used_backend: BackendId | None,
    merged_currency: str | None,
    role: str,
    expected: bool,
):
    assert (
        _would_escalate_shell(
            scrape_tier=scrape_tier,
            used_backend=used_backend,
            merged_currency=merged_currency,
            role=role,
        )
        is expected
    )
