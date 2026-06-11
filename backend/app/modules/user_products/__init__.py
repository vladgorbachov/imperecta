"""User-products module - intentionally empty.

The previous v2-migration stubs (api_products / api_competitors / api_import /
service / schemas / models) were deleted in UP1. The full implementation -
user file upload routed through the shared Ingestion rail, the user<->product
link flag, the 2GB quota, the hide-products option - is rebuilt in Phase 4
together with the Ingestion module, because user products will ride the same
parse/dedup/merge rails as parser products and that shared machinery does not
exist yet. Competitor management leaves this module entirely; a future
Analytics module owns competitors when it is built.

Until Phase 4 the package exposes no routes, services, schemas, or Celery
tasks. The DB tables (DimProduct / UserProduct) remain untouched.
"""
