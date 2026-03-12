"""Market data provider adapters."""

from app.services.market_data.providers.base import (
    CommoditiesProviderAdapter,
    CryptoProviderAdapter,
    ForexProviderAdapter,
)
from app.services.market_data.providers.commodities_adapter import (
    CommoditiesHttpAdapter,
)
from app.services.market_data.providers.crypto_adapter import CryptoCoingeckoAdapter
from app.services.market_data.providers.forex_adapter import ForexFrankfurterAdapter

__all__ = [
    "ForexProviderAdapter",
    "CryptoProviderAdapter",
    "CommoditiesProviderAdapter",
    "ForexFrankfurterAdapter",
    "CryptoCoingeckoAdapter",
    "CommoditiesHttpAdapter",
]
