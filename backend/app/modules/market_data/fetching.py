"""Thin provider-wrapper helpers for live HTTP fetches.

After M2 there is no in-memory cache; each call delegates straight to the
relevant adapter in `providers/` and maps DTOs to the dict shapes consumed by
`api.py` (DB-empty fallback branch) and `ingestion.py` (scheduled persist).

The tuple shapes returned by `fetch_crypto_prices` / `fetch_commodities` retain
their historical second/third element (`from_cache`) for backward compatibility
with existing call-sites; the flag is now always `False`.
"""

import logging

logger = logging.getLogger(__name__)


async def fetch_forex_rates(base: str = "EUR") -> list[dict]:
    """Fetch forex rates via ForexUnifiedAdapter. Empty list on provider failure.

    Cache removed in M2: DB facts hold the last snapshot, and `api.py` reads
    them first; this thin wrapper exists only for ingestion + DB-empty fallback.
    """
    from app.modules.market_data.providers.forex_adapter import ForexUnifiedAdapter

    try:
        adapter = ForexUnifiedAdapter(timeout=15.0)
        items = await adapter.fetch()
    except Exception as error:
        logger.error("Forex unified provider error: %s", error)
        return []

    base_prefix = f"{base.upper()}/"
    normalized: list[dict] = []
    for dto in items:
        pair = dto.symbol.upper()
        if not pair.startswith(base_prefix):
            continue
        normalized.append({
            "pair": pair,
            "rate": round(float(dto.bid), 6),
            "change_24h": dto.change_24h,
        })
    normalized.sort(key=lambda row: row["pair"])
    logger.info("Forex rates fetched via unified adapter: %d pairs (base=%s)", len(normalized), base)
    return normalized


async def fetch_crypto_prices() -> tuple[list[dict], bool]:
    """Fetch crypto via CryptoUnifiedAdapter.

    Returns (items, from_cache). After M2 the second element is always False
    because the in-memory cache was removed; the tuple shape is kept for
    backward compatibility with callers (api.py, ingestion.py).
    """
    from app.modules.market_data.providers.crypto_adapter import CryptoUnifiedAdapter

    adapter = CryptoUnifiedAdapter(timeout=15.0)
    items = await adapter.fetch()
    result = [
        {
            "symbol": dto.symbol,
            "name": dto.symbol,
            "price": float(dto.price),
            "change_24h": round(dto.change_24h, 2) if dto.change_24h is not None else None,
            "market_cap": float(dto.market_cap) if dto.market_cap is not None else None,
            "volume_24h": None,
            "image": "",
        }
        for dto in items
    ]
    logger.info("Crypto prices fetched: %d coins", len(result))
    return (result, False)


async def fetch_commodities() -> tuple[list[dict], str | None, bool]:
    """Fetch commodities via CommoditiesUnifiedAdapter.

    Returns (items, error_message, from_cache). After M2 the third element is
    always False (cache removed); the tuple shape is preserved for callers.
    """
    from app.modules.market_data.providers.commodities_adapter import CommoditiesUnifiedAdapter

    try:
        adapter = CommoditiesUnifiedAdapter(timeout=15.0)
        items = await adapter.fetch()
    except Exception as error:
        logger.warning("Unified commodities fetch failed: %s", error)
        return ([], "Commodities providers unavailable (Gold API and Alpha Vantage/Yahoo)", False)

    normalized_items = [
        {
            "name": dto.name or dto.symbol,
            "symbol": dto.symbol,
            "price": float(dto.price),
            "unit": dto.unit or "",
            "change_24h": dto.change_24h,
        }
        for dto in items
    ]
    if not normalized_items:
        return ([], "Commodities providers unavailable (Gold API and Alpha Vantage/Yahoo)", False)
    return (normalized_items, None, False)
