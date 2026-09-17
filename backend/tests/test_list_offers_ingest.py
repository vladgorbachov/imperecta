"""Price-from-list ingestion (slice 2): matching, counters, sparse data shape."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.main import app
from app.models.facts import FactListing
from app.modules.ingestion import list_offers as lo


def _offer(url, price=99.5, currency="EUR", title="Widget"):
    return {
        "url": url,
        "price": price,
        "currency": currency,
        "title": title,
        "price_raw_text": f"{title} {price} {currency}",
    }


def _db_with_listings(urls):
    listings = {}
    for url in urls:
        h = FactListing.compute_url_hash(url)
        listings[h] = SimpleNamespace(url_hash=h, external_url=url)
    db = MagicMock()
    db.execute.return_value.scalars.return_value = list(listings.values())
    return db


def test_matches_known_urls_and_counts_unknown():
    known = "https://shop.example/p/known-1"
    db = _db_with_listings([known])
    persisted = SimpleNamespace(persisted=True, log_status="success")
    with patch.object(lo.IngestionService, "persist_extracted", return_value=persisted) as pe:
        counters = lo.ingest_list_offers(
            db,
            offers=[_offer(known), _offer("https://shop.example/p/stranger-2")],
        )
    assert counters == {"matched": 1, "saved": 1, "unknown": 1, "unpriced": 0}
    data = pe.call_args.kwargs["data"]
    assert data.title == "Widget"
    assert data.price == 99.5
    assert data.currency == "EUR"
    assert data.page_role == "product"
    assert data.image_url is None and data.brand is None  # sparse by design


def test_no_change_counts_as_saved():
    known = "https://shop.example/p/known-1"
    db = _db_with_listings([known])
    unchanged = SimpleNamespace(persisted=False, log_status="no_change")
    with patch.object(lo.IngestionService, "persist_extracted", return_value=unchanged):
        counters = lo.ingest_list_offers(db, offers=[_offer(known)])
    assert counters["saved"] == 1


def test_priceless_offer_matched_but_not_ingested():
    known = "https://shop.example/p/known-1"
    db = _db_with_listings([known])
    with patch.object(lo.IngestionService, "persist_extracted") as pe:
        counters = lo.ingest_list_offers(db, offers=[_offer(known, price=None)])
    pe.assert_not_called()
    assert counters == {"matched": 1, "saved": 0, "unknown": 0, "unpriced": 1}


def test_empty_offers_short_circuit():
    db = MagicMock()
    assert lo.ingest_list_offers(db, offers=[])["matched"] == 0
    db.execute.assert_not_called()


def test_harvest_endpoint_registered():
    schema = app.openapi()
    entry = schema["paths"].get("/api/admin/parsing/harvest-lists", {})
    assert "post" in entry


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("imperecta_core") is None,
    reason="rust core not built in this environment",
)
def test_rust_list_offers_parity_shape():
    import imperecta_core as ic

    html = "<html><body>" + "".join(
        f'<div class="card"><a href="/p/w-{i}">Widget {i}</a>'
        f"<span>1 299,{i:02d} €</span></div>"
        for i in range(7)
    ) + "</body></html>"
    offers = ic.extract_list_offers(html, "https://shop.example/c/x")
    assert len(offers) == 7
    first = offers[0]
    assert first["url"] == "https://shop.example/p/w-0"
    assert first["price"] == 1299.0
    assert first["currency"] == "EUR"
    assert first["title"] == "Widget 0"
