"""Fuel-price view helpers.

`get_fuel_prices` returns a country-scoped legacy-shaped dict assembled from
`fact_fuel_price` rows. Reads are delegated to `reader.MarketDataService`.
"""

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.market_data.reader import MarketDataService


def _fuel_facts_to_legacy_dict(rows: list[dict[str, Any]], country_code: str) -> dict[str, Any]:
    """Map fact_fuel_price rows to legacy flat dict used by dashboard clients."""
    currency = rows[0]["currency_code"]
    label = country_code
    fetched = rows[0].get("fetched_at")
    if isinstance(fetched, datetime):
        updated_str = fetched.isoformat()
    else:
        updated_str = str(fetched) if fetched else ""
    out: dict[str, Any] = {
        "country": label,
        "currency": currency,
        "unit": "L",
        "updated": updated_str,
    }
    for r in rows:
        out[r["fuel_type"]] = r["price_local"]
    return out


async def get_fuel_prices(country_code: str, db: AsyncSession | None = None) -> dict | None:
    """Get fuel prices from fact_fuel_price only (requires db session)."""
    code = country_code.upper()
    if db is None:
        return None
    mds = MarketDataService(db)
    raw = await mds.get_fuel(code)
    if raw:
        return _fuel_facts_to_legacy_dict(raw, code)
    return None
