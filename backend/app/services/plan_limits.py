"""Plan limits. Delegates to entitlements module."""

from app.entitlements import get_limit, get_service_tier
from app.entitlements.plan import ServiceTier
from app.models.user import UserPlan


def get_product_limit(plan: UserPlan) -> int:
    """Max products allowed for plan."""
    return get_limit(plan, "products")


def get_competitor_limit(plan: UserPlan) -> int:
    """Max competitors allowed for plan."""
    return get_limit(plan, "competitors")


def is_free_plan(plan: UserPlan) -> bool:
    """True if plan has product limit enforcement (Free tier only). Trial has full access."""
    tier = get_service_tier(plan)
    return tier == ServiceTier.FREE
