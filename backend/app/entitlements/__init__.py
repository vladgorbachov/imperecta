"""
Plan and entitlement architecture for service tier separation.

Service tiers: Trial, Free, Paid Full.
Single source of truth for limits, feature access, and trial behavior.
"""

from app.entitlements.plan import (
    Feature,
    ServiceTier,
    get_entitlements_for_frontend,
    get_limit,
    get_service_tier,
    has_feature,
    is_free,
    is_paid,
    is_trial,
    is_trial_expired,
)

__all__ = [
    "Feature",
    "ServiceTier",
    "get_entitlements_for_frontend",
    "get_limit",
    "get_service_tier",
    "has_feature",
    "is_free",
    "is_paid",
    "is_trial",
    "is_trial_expired",
]
