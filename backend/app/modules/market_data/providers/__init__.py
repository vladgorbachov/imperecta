"""Market data provider adapters."""

from app.modules.market_data.providers.base import (
    CommoditiesProviderAdapter,
    CryptoProviderAdapter,
    ForexProviderAdapter,
)
from app.modules.market_data.providers.binance_adapter import BinanceCryptoAdapter
from app.modules.market_data.providers.commodities_adapter import CommoditiesUnifiedAdapter
from app.modules.market_data.providers.crypto_adapter import (
    CryptoCoingeckoAdapter,
    CryptoCompositeAdapter,
    CryptoUnifiedAdapter,
)
from app.modules.market_data.providers.forex_adapter import ForexFrankfurterAdapter, ForexUnifiedAdapter

__all__ = [
    "ForexProviderAdapter",
    "CryptoProviderAdapter",
    "CommoditiesProviderAdapter",
    "ForexFrankfurterAdapter",
    "ForexUnifiedAdapter",
    "CryptoCoingeckoAdapter",
    "CryptoCompositeAdapter",
    "CryptoUnifiedAdapter",
    "BinanceCryptoAdapter",
    "CommoditiesUnifiedAdapter",
]
