"""API route handlers - all routers registered here."""

from fastapi import APIRouter

from app.api import auth, products, competitors, analytics, alerts, digests, import_export

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(competitors.router, prefix="/competitors", tags=["competitors"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(digests.router, prefix="/digests", tags=["digests"])
api_router.include_router(import_export.router, prefix="/import", tags=["import"])
