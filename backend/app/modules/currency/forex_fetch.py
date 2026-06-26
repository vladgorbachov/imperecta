"""Live EUR-base forex fetch owned by the currency module."""

from __future__ import annotations


async def fetch_eur_base_pairs() -> list[dict]:
    """Return EUR-base forex rows via the market-data provider queue."""
    from app.modules.market_data.fetching import fetch_forex_rates

    return await fetch_forex_rates("EUR")
