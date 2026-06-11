"""Product pool module - read-surface over the global pool.

Public surface:
    - api.router: `/pool/*` endpoints (list/categories/marketplace-stats/stats/search).
    - api.markets_overview_router: `/markets/overview` endpoint, preserved
      verbatim from the dissolved dashboard module.
    - service.ProductPoolService: SQL queries over the v2 star schema
      (DimProduct, DimMarketplace, FactListing, FactPrice, DimDate).

Canonical ORM models live in app.models, not here. This module is read-only:
all writes happen via the scraper pipeline (Phase 4) and admin marketplaces
CRUD (`app.modules.marketplaces`).
"""
