"""Adaptive scrape backoff (slice 3): interval growth/reset + gate allowlist."""

from __future__ import annotations

from app.modules.data_firewall.update_validator import SCRAPE_UPDATE_ALLOWLIST
from app.modules.ingestion.service import (
    BASE_SCRAPE_INTERVAL_MINUTES,
    MAX_SCRAPE_INTERVAL_MINUTES,
    next_scrape_interval,
)


def test_unchanged_price_doubles_interval():
    assert next_scrape_interval(360, price_changed=False) == 720
    assert next_scrape_interval(720, price_changed=False) == 1440


def test_interval_capped_at_seven_days():
    assert next_scrape_interval(9000, price_changed=False) == MAX_SCRAPE_INTERVAL_MINUTES
    assert (
        next_scrape_interval(MAX_SCRAPE_INTERVAL_MINUTES, price_changed=False)
        == MAX_SCRAPE_INTERVAL_MINUTES
    )


def test_price_change_resets_to_base():
    assert next_scrape_interval(10_080, price_changed=True) == BASE_SCRAPE_INTERVAL_MINUTES
    assert next_scrape_interval(None, price_changed=True) == BASE_SCRAPE_INTERVAL_MINUTES


def test_missing_or_corrupt_interval_falls_back_to_base():
    assert next_scrape_interval(None, price_changed=False) == 720
    assert next_scrape_interval(0, price_changed=False) == 720
    assert next_scrape_interval(15, price_changed=False) == 720  # below base → base*2


def test_gate_allows_interval_on_both_denorm_kinds():
    listing_kinds = SCRAPE_UPDATE_ALLOWLIST["fact_listing"]
    assert "scrape_interval_minutes" in listing_kinds["listing_denorm_success"]
    assert "scrape_interval_minutes" in listing_kinds["listing_denorm_no_change"]
