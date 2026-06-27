"""Pure-logic tests for discovery cursor_store (no DB/network)."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.modules.discovery import cursor_store


def _stub_marketplace(**overrides: object) -> SimpleNamespace:
    """Minimal marketplace stand-in with cursor fields."""
    defaults: dict[str, object] = {
      "id": uuid4(),
      "base_url": "https://shop.example",
      "last_sitemap_harvest_at": None,
      "sitemap_url": None,
      "recon_frontier_state": None,
      "discovered_category_urls": [],
      "category_resume_index": 0,
      "sitemap_resume_offset": 0,
      "sitemap_bad_harvest_streak": 0,
      "phase1_exhausted_streak": 0,
      "last_discovery_at": None,
      "last_discovery_status": None,
      "last_discovery_products_found": 0,
      "products_in_pool": 0,
      "last_category_recon_at": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_serialize_parse_frontier_round_trip_queue_pairs_and_visited_set() -> None:
    queue = deque([("https://shop.example/a", 0), ("https://shop.example/b", 1)])
    visited = {"https://shop.example", "https://shop.example/a"}
    listing_urls = ["https://shop.example/listing-1"]

    serialized = cursor_store.serialize_frontier(queue, visited, listing_urls)
    assert serialized == {
        "queue": [
            ["https://shop.example/a", 0],
            ["https://shop.example/b", 1],
        ],
        "visited": [
            "https://shop.example",
            "https://shop.example/a",
        ],
        "listing_urls": ["https://shop.example/listing-1"],
    }
    assert isinstance(serialized["visited"], list)

    parsed_queue, parsed_visited, parsed_listing_urls = cursor_store.parse_frontier(
        serialized,
    )
    assert list(parsed_queue) == list(queue)
    assert parsed_visited == visited
    assert isinstance(parsed_visited, set)
    assert parsed_listing_urls == listing_urls


def test_apply_frontier_and_clear_frontier_on_stub_marketplace() -> None:
    marketplace = _stub_marketplace()
    queue = deque([("https://shop.example/cat", 2)])
    visited = {"https://shop.example"}

    cursor_store.apply_frontier(
        marketplace,
        queue,
        visited,
        [],
    )
    assert marketplace.recon_frontier_state == {
        "queue": [["https://shop.example/cat", 2]],
        "visited": ["https://shop.example"],
        "listing_urls": [],
    }

    cursor_store.clear_frontier(marketplace)
    assert marketplace.recon_frontier_state is None


def test_publish_path_shape_matches_prod_frontier_contract() -> None:
    """Serialized dict uses queue pairs, visited list, listing_urls list only."""
    queue = deque([("https://pandashop.md/ru/catalog/", 1)])
    visited = {"https://pandashop.md"}

    payload = cursor_store.serialize_frontier(queue, visited, [])
    assert set(payload.keys()) == {"queue", "visited", "listing_urls"}
    assert payload["queue"] == [["https://pandashop.md/ru/catalog/", 1]]
    assert payload["visited"] == ["https://pandashop.md"]
    assert payload["listing_urls"] == []


def test_int_cursors_and_category_urls_round_trip() -> None:
    marketplace = _stub_marketplace()
    now = datetime.now(tz=timezone.utc)

    cursor_store.set_sitemap_resume_offset(marketplace, 42)
    cursor_store.set_sitemap_bad_harvest_streak(marketplace, 2)
    cursor_store.set_category_resume_index(marketplace, 7)
    cursor_store.set_discovered_category_urls(
        marketplace,
        ["https://shop.example/c1", "https://shop.example/c2"],
    )
    cursor_store.set_last_category_recon_at(marketplace, now)
    cursor_store.set_last_sitemap_harvest_at(marketplace, now)
    cursor_store.set_sitemap_url(marketplace, "https://shop.example/sitemap.xml")

    assert cursor_store.get_sitemap_resume_offset(marketplace) == 42
    assert cursor_store.get_sitemap_bad_harvest_streak(marketplace) == 2
    assert cursor_store.get_category_resume_index(marketplace) == 7
    assert cursor_store.get_discovered_category_urls(marketplace) == [
        "https://shop.example/c1",
        "https://shop.example/c2",
    ]
    assert cursor_store.get_last_category_recon_at(marketplace) == now
    assert cursor_store.get_last_sitemap_harvest_at(marketplace) == now
    assert cursor_store.get_sitemap_url(marketplace) == "https://shop.example/sitemap.xml"


def test_snapshot_meta_columns_returns_discovery_mp_write_keys_subset() -> None:
    now = datetime.now(timezone.utc)
    marketplace = _stub_marketplace(
        last_discovery_status="partial_budget",
        products_in_pool=12,
        last_category_recon_at=now,
        recon_frontier_state={"queue": [], "visited": [], "listing_urls": []},
    )

    snapshot = cursor_store.snapshot_meta_columns(marketplace)

    assert set(snapshot.keys()) == set(cursor_store.DISCOVERY_MP_WRITE_KEYS)
    assert snapshot["last_discovery_status"] == "partial_budget"
    assert snapshot["products_in_pool"] == 12
    assert snapshot["base_url"] == "https://shop.example"
    assert snapshot["last_category_recon_at"] == now


def test_safe_parse_frontier_valid_matches_parse_frontier() -> None:
    serialized = cursor_store.serialize_frontier(
        deque([("https://shop.example/a", 0)]),
        {"https://shop.example"},
        ["https://shop.example/listing-1"],
    )
    marketplace = _stub_marketplace(recon_frontier_state=serialized)

    (
        safe_queue,
        safe_visited,
        safe_listing,
        was_corrupted,
        error_kind,
    ) = cursor_store.safe_parse_frontier(marketplace)
    parsed_queue, parsed_visited, parsed_listing = cursor_store.parse_frontier(
        serialized,
    )

    assert was_corrupted is False
    assert error_kind is None
    assert list(safe_queue) == list(parsed_queue)
    assert safe_visited == parsed_visited
    assert safe_listing == parsed_listing


def test_safe_parse_frontier_corrupt_queue_item_cold_starts() -> None:
    marketplace = _stub_marketplace(
        recon_frontier_state={
            "queue": [["https://shop.example/bad"]],
            "visited": ["https://shop.example"],
            "listing_urls": [],
        },
        category_resume_index=4,
    )

    queue, visited, listing_urls, was_corrupted, error_kind = (
        cursor_store.safe_parse_frontier(marketplace)
    )

    assert was_corrupted is True
    assert error_kind == "queue_item_invalid"
    assert marketplace.recon_frontier_state is None
    assert marketplace.category_resume_index == 0
    assert list(queue) == [("https://shop.example", 0)]
    assert visited == {"https://shop.example"}
    assert listing_urls == []


def test_safe_parse_frontier_visited_not_list_cold_starts() -> None:
    marketplace = _stub_marketplace(
        recon_frontier_state={
            "queue": [],
            "visited": "not-a-list",
            "listing_urls": [],
        },
    )

    _, _, _, was_corrupted, error_kind = cursor_store.safe_parse_frontier(
        marketplace,
    )

    assert was_corrupted is True
    assert error_kind == "visited_not_list"
    assert marketplace.recon_frontier_state is None


def test_safe_parse_frontier_parse_raises_cold_starts(monkeypatch) -> None:
    marketplace = _stub_marketplace(
        recon_frontier_state={
            "queue": [],
            "visited": [],
            "listing_urls": [],
        },
    )

    def _boom(_saved: object) -> tuple:
        raise RuntimeError("parse boom")

    monkeypatch.setattr(cursor_store, "parse_frontier", _boom)

    _, _, _, was_corrupted, error_kind = cursor_store.safe_parse_frontier(
        marketplace,
    )

    assert was_corrupted is True
    assert error_kind == "parse_failed"
