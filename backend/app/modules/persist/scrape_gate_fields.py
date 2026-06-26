"""Field assembly for scrape gate UPDATE/DELETE payloads (no validation)."""

from __future__ import annotations

from typing import Any
from uuid import UUID


def build_listing_update_fields(*, url_hash: str, **delta: Any) -> dict[str, Any]:
    """Locator + changed fact_listing columns for authorize_scrape_update."""
    return {"url_hash": url_hash, **delta}


def build_product_update_fields(*, product_id: UUID | str, **delta: Any) -> dict[str, Any]:
    """Locator + changed dim_product columns for authorize_scrape_update."""
    pid = product_id if isinstance(product_id, str) else str(product_id)
    return {"id": pid, **delta}


def build_listing_delete_fields(*, url_hash: str) -> dict[str, Any]:
    """Locator-only payload for fact_listing DELETE."""
    return {"url_hash": url_hash}


def build_product_delete_fields(*, product_id: UUID | str) -> dict[str, Any]:
    """Locator-only payload for dim_product DELETE."""
    pid = product_id if isinstance(product_id, str) else str(product_id)
    return {"id": pid}
