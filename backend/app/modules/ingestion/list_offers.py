"""Price-from-list ingestion (SITEMAP_FIRST slice 2).

One category/list page carries prices for dozens of products; the Rust core
(`imperecta_core.extract_list_offers`) turns it into (url, price, currency,
title) offers, and this module routes each offer through the SAME
`IngestionService.persist_extracted` path a card scrape uses — so the
data_firewall, currency disambiguation, price_eur resolution, no-change
dedupe and the quality gate all apply unchanged. A list offer is just a
sparse ExtractedProduct: title+price+currency present, everything else None.

Offers whose URL is not in the pool yet are counted (``unknown``) — and,
when they carry both a title and a price (i.e. they sit in a real product
card), onboarded as new pool pairs through the same discovery gate path the
sitemap enumerator uses. List pages thus close the coverage gap sitemap
filters leave (techmart: 5k of ~18k slugs), with better titles for free.
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


def _normalize_name(name: str) -> str:
    return " ".join((name or "").lower().split())[:500]


def _onboard_unknown_offers(
    unknown_offers: list[dict[str, Any]],
    hash_by_url: dict[str, str],
    marketplace_id,
) -> int:
    """Insert product-card offers the pool has never seen, via the gate.

    Only offers with BOTH a title and a price qualify — that combination
    only occurs inside a real product card, so this cannot onboard nav or
    facet links. Returns the number of pairs the gate accepted.
    """
    from uuid import uuid4

    from app.modules.discovery.gate_persist import PoolInsertDTO, write_pool_dtos_sync
    from app.modules.persist.writer import (
        build_dim_product_fields,
        build_fact_listing_fields,
    )

    dtos: list[PoolInsertDTO] = []
    seen: set[str] = set()
    for offer in unknown_offers:
        title = (offer.get("title") or "").strip()
        if not title or offer.get("price") is None:
            continue
        url = str(offer["url"])
        url_hash = hash_by_url[url]
        if url_hash in seen:
            continue
        seen.add(url_hash)
        product_id = uuid4()
        product_fields: dict[str, Any] = {
            "name": title[:500],
            "name_normalized": _normalize_name(title) or "product",
            "is_active": True,
        }
        image_url = offer.get("image_url")
        if isinstance(image_url, str) and image_url.strip():
            product_fields["image_url"] = image_url.strip()[:2000]
        dtos.append(
            PoolInsertDTO(
                marketplace_id=marketplace_id,
                dim_product=build_dim_product_fields(
                    product_id=product_id,
                    **product_fields,
                ),
                fact_listing=build_fact_listing_fields(
                    product_id=product_id,
                    marketplace_id=marketplace_id,
                    external_url=url,
                    url_hash=url_hash,
                    is_active=True,
                    page_role="product",
                ),
            )
        )
    if not dtos:
        return 0
    return write_pool_dtos_sync(dtos).inserted


def ingest_list_offers(
    db: Session,
    *,
    offers: list[dict[str, Any]],
    scrape_job_id=None,
    marketplace_id=None,
) -> dict[str, int]:
    """Persist prices from list offers onto existing pool listings.

    Returns counters: matched / priced / no_change_or_saved / unknown /
    unpriced. Commits are owned by IngestionService per offer (decision A).
    """
    if not offers:
        return {
            "matched": 0,
            "saved": 0,
            "unknown": 0,
            "unpriced": 0,
            "suspicious": 0,
            "onboarded": 0,
        }

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
    unknown_offers: list[dict[str, Any]] = []
    for offer in offers:
        url = str(offer.get("url") or "")
        url_hash = hash_by_url.get(url)
        listing = listing_by_hash.get(url_hash) if url_hash else None
        if listing is None:
            unknown += 1
            if url_hash is not None:
                unknown_offers.append(offer)
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
            # Card thumbnail: write-once image fill for products whose PDP
            # was never scraped (99.9% of the sitemap-onboarded pool).
            image_url=offer.get("image_url"),
        )
        result = service.persist_extracted(
            data=data,
            listing=listing,
            scrape_job_id=scrape_job_id,
        )
        if result.persisted or result.log_status == "no_change":
            saved += 1

    onboarded = 0
    if marketplace_id is not None and unknown_offers:
        onboarded = _onboard_unknown_offers(unknown_offers, hash_by_url, marketplace_id)

    counters = {
        "matched": matched,
        "saved": saved,
        "unknown": unknown,
        "unpriced": unpriced,
        "suspicious": suspicious,
        "onboarded": onboarded,
    }
    slog.info("list_offers_ingested", **counters)
    return counters
