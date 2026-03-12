"""Abstract provider adapters. Provider-specific shapes stay inside adapters."""

from abc import ABC, abstractmethod
from datetime import datetime

from app.services.market_data.dto import (
    NormalizedCommodity,
    NormalizedCrypto,
    NormalizedForex,
)


class ForexProviderAdapter(ABC):
    """Abstract forex provider. Returns normalized DTOs only."""

    @abstractmethod
    async def fetch(self) -> list[NormalizedForex]:
        """Fetch and normalize forex data. Raises on parse/validation failure."""
        ...


class CryptoProviderAdapter(ABC):
    """Abstract crypto provider. Returns normalized DTOs only."""

    @abstractmethod
    async def fetch(self) -> list[NormalizedCrypto]:
        """Fetch and normalize crypto data. Raises on parse/validation failure."""
        ...


class CommoditiesProviderAdapter(ABC):
    """Abstract commodities provider. Returns normalized DTOs only."""

    @abstractmethod
    async def fetch(self) -> list[NormalizedCommodity]:
        """Fetch and normalize commodities data. Raises on parse/validation failure."""
        ...
