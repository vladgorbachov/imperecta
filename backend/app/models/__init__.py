"""
Re-export all ORM models for Alembic metadata discovery.
Actual model code lives in app/modules/*/models.py.
"""

# Core
# AI
from app.modules.ai_analyst.models import AIChatMessage, AIChatSession

# Alerts
from app.modules.alerts.models import Alert, AlertEvent
from app.modules.core.models import ApiLog, User, UserPlan

# Digests
from app.modules.digests.models import Digest

# Market Data
from app.modules.market_data.models import (
    MarketsCategoryAnalytics,
    MarketsCommodity,
    MarketsCrypto,
    MarketsForex,
    MarketsMarketplaceAnalytics,
    MarketsOpportunityBlock,
    MarketsPreferences,
    MarketsRefreshLog,
    MarketsRefreshStatus,
    MarketsRefreshType,
    MarketsTickerItem,
)

# Marketplaces
from app.modules.marketplaces.models import AdminMarketplace

# Product Pool
from app.modules.product_pool.models import GlobalPriceSnapshot, GlobalProduct

# Scraper
from app.modules.scraper.models import DiscoveryLog, ScrapeLog

# User Products
from app.modules.user_products.models import (
    Competitor,
    CompetitorProduct,
    PriceSnapshot,
    Product,
)

__all__ = [
    "AdminMarketplace",
    "AIChatMessage",
    "AIChatSession",
    "ApiLog",
    "User",
    "UserPlan",
    "ApiLog",
    "AdminMarketplace",
    "GlobalProduct",
    "GlobalPriceSnapshot",
    "ScrapeLog",
    "DiscoveryLog",
    "Product",
    "Competitor",
    "CompetitorProduct",
    "PriceSnapshot",
    "Alert",
    "AlertEvent",
    "Digest",
    "MarketsPreferences",
    "MarketsRefreshLog",
    "MarketsRefreshStatus",
    "MarketsRefreshType",
    "MarketsForex",
    "MarketsCrypto",
    "MarketsCommodity",
    "MarketsTickerItem",
    "MarketsCategoryAnalytics",
    "MarketsMarketplaceAnalytics",
    "MarketsOpportunityBlock",
    "AIChatSession",
    "AIChatMessage",
]
