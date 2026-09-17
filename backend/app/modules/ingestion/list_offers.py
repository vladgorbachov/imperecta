"""Price-from-list ingestion (SITEMAP_FIRST slice 2).

One category/list page carries prices for dozens of products; the Rust core
(`imperecta_core.extract_list_offers`) turns it into (url, price, currency,
title) offers, and this module routes each offer through the SAME
`IngestionService.persist_extracted` path a card scrape uses — so the
data_firewall, currency disambiguation, price_eur resolution, no-change
dedupe and the quality gate all apply unchanged. A list offer is just a
sparse ExtractedProduct: title+price+currency present, everything else None.

Offers whose URL is not in the pool yet are counted (``unknown``) and
skipped — onboarding is the sitemap enumerator's job, not the harvester's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.facts import FactListing
from app.modules.ingestion.service import IngestionService

slog = structlog.get_logger(__name__)

# A list page is a lower-trust context than a product card: extraction noise
# (a neighbouring card's price, a bundle price) is possible even with
# currency-anchored parsing. A price that jumps this far from the listing's
# known last_price is held back for the next card scrape to arbitrate.
SUSPICIOUS_PRICE_RATIO = 5.0


def _price_is_suspicious(new_price: float, last_price) -> bool:
    if last_price is None:
        return False
    try:
        prior = float(last_price)
    except (TypeError, ValueError):
        return False
    if prior <= 0 or new_price <= 0:
        return False
    ratio = new_price / prior
    return ratio > SUSPICIOUS_PRICE_RATIO or ratio < 1 / SUSPICIOUS_PRICE_RATIO


@dataclass
class ListOfferData:
    """Duck-typed ExtractedProduct subset produced by the list harvester."""

    title: str | None = None
    price: float | None = None
    original_price: float | None = None
    currency: str | None = None
    currency_raw: str | None = None
    price_raw_text: str | None = None
    image_url: str | None = None
    description: str | None = None
    brand: str | None = None
    category_path: list[str] | None = None
    product_name: str | None = None
    page_role: str | None = "product"


def ingest_list_offers(
    db: Session,
    *,
    offers: list[dict[str, Any]],
    scrape_job_id=None,
) -> dict[str, int]:
    """Persist prices from list offers onto existing pool listings.

    Returns counters: matched / priced / no_change_or_saved / unknown /
    unpriced. Commits are owned by IngestionService per offer (decision A).
    """
    if not offers:
        return {"matched": 0, "saved": 0, "unknown": 0, "unpriced": 0, "suspicious": 0}

    hash_by_url = {
        str(offer["url"]): FactListing.compute_url_hash(str(offer["url"]))
        for offer in offers
        if offer.get("url")
    }
    rows = db.execute(
        select(FactListing).where(
            FactListing.url_hash.in_(list(hash_by_url.values()))
        )
    ).scalars()
    listing_by_hash = {row.url_hash: row for row in rows}

    service = IngestionService(db)
    matched = saved = unknown = unpriced = suspicious = 0
    for offer in offers:
        url = str(offer.get("url") or "")
        url_hash = hash_by_url.get(url)
        listing = listing_by_hash.get(url_hash) if url_hash else None
        if listing is None:
            unknown += 1
            continue
        matched += 1
        if offer.get("price") is None:
            unpriced += 1
            continue
        if _price_is_suspicious(float(offer["price"]), listing.last_price):
            suspicious += 1
            slog.info(
                "list_offer_suspicious_price",
                url=url,
                offer_price=offer["price"],
                last_price=str(listing.last_price),
            )
            continue
        data = ListOfferData(
            title=offer.get("title"),
            price=offer.get("price"),
            currency=offer.get("currency"),
            currency_raw=offer.get("currency"),
            price_raw_text=offer.get("price_raw_text"),
        )
        result = service.persist_extracted(
            data=data,
            listing=listing,
            scrape_job_id=scrape_job_id,
        )
        if result.persisted or result.log_status == "no_change":
            saved += 1

    counters = {
        "matched": matched,
        "saved": saved,
        "unknown": unknown,
        "unpriced": unpriced,
        "suspicious": suspicious,
    }
    slog.info("list_offers_ingested", **counters)
    return counters
