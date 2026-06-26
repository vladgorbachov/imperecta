"""User-scoped facade over the market_data internals.

`MarketsService` is the entry point used by `api.py /markets/*` and the C3
analytics routes on `dashboard/api.py`. It owns the user-id context, delegates
DB reads to `reader.MarketDataService`, and exposes the legacy preference and
instrument-listing dicts unchanged.
"""

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import User
from app.modules.market_data.reader import MarketDataService


class MarketsService:
    """Markets domain: user preferences (JSONB) and instrument lists for ticker widgets."""

    _PREF_KEYS = frozenset({
        "dashboard_widgets",
        "forex_favorites",
        "crypto_favorites",
        "commodity_favorites",
        "favorite_instrument_ids",
    })

    def __init__(self, db: AsyncSession, user_id):
        self.db = db
        self.user_id = user_id

    async def _get_user(self) -> User:
        result = await self.db.execute(select(User).where(User.id == self.user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError("User not found")
        return user

    async def get_preferences(self) -> dict:
        user = await self._get_user()
        mds = MarketDataService(self.db)
        return await mds.get_preferences(user)

    async def update_preferences(self, **updates: Any) -> dict:
        user = await self._get_user()
        mds = MarketDataService(self.db)
        clean = {k: v for k, v in updates.items() if k in self._PREF_KEYS and v is not None}
        return await mds.update_preferences(user, clean)

    async def get_available_instruments(self) -> dict[str, list[dict[str, str]]]:
        """Return available instrument lists for user-configurable ticker widgets."""
        mds = MarketDataService(self.db)
        forex, crypto, commodities = await asyncio.gather(
            mds.get_available_forex_instruments(),
            mds.get_available_crypto_instruments(),
            mds.get_available_commodity_instruments(),
        )
        return {
            "forex": forex,
            "crypto": crypto,
            "commodities": commodities,
        }
