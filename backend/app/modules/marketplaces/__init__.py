"""Marketplaces module - dim_marketplace admin CRUD + pipeline quota helpers.

Public surface:
    - api.router: admin CRUD endpoints under /admin/marketplaces.
    - service.MarketplaceService: admin CRUD operations.
    - service.MarketplacePoolService: pipeline-side products_in_pool maintenance
      (called from scraper.tasks).
    - service.DEFAULT_TOTAL_POOL_SIZE: named pool capacity constant.

Canonical ORM models (DimMarketplace, DimCountry, DimCurrency, ScrapeLog) live
in app.models, not here. This module owns admin write paths and the pipeline
quota helper only.
"""
