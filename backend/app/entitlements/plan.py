"""
Plan and entitlement definitions.

Service tiers: Trial, Free, Paid Full.
Maps from UserPlan (DB) to ServiceTier (canonical business logic).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.models.user import UserPlan


class ServiceTier(str, Enum):
    """Canonical service tier. Single source of truth for tier behavior."""

    TRIAL = "trial"
    FREE = "free"
    PAID_FULL = "paid_full"


class Feature(str, Enum):
    """Feature flags for entitlement checks. Extend as business matrix is defined."""

    AI_ANALYST = "ai_analyst"
    # Placeholder for future features
    # DAILY_DIGEST = "daily_digest"
    # ADVANCED_ANALYTICS = "advanced_analytics"


# Trial duration in days
TRIAL_DURATION_DAYS = 14

# UserPlan -> ServiceTier mapping
PLAN_TO_TIER: dict[UserPlan, ServiceTier] = {
    UserPlan.trial: ServiceTier.TRIAL,
    UserPlan.starter: ServiceTier.FREE,
    UserPlan.business: ServiceTier.PAID_FULL,
    UserPlan.pro: ServiceTier.PAID_FULL,
}

# ServiceTier -> feature access. True = enabled, False = disabled.
# Extend as feature matrix is defined.
FEATURE_ENTITLEMENTS: dict[ServiceTier, dict[Feature, bool]] = {
    ServiceTier.TRIAL: {
        Feature.AI_ANALYST: False,  # Trial: full platform except AI Analyst
    },
    ServiceTier.FREE: {
        Feature.AI_ANALYST: False,  # Free: restricted
    },
    ServiceTier.PAID_FULL: {
        Feature.AI_ANALYST: True,  # Paid Full: all features
    },
}

# ServiceTier -> usage limits. Extend as limits are defined.
# Trial: full platform except AI Analyst -> no product limit during trial.
# Free: restricted -> 50 products.
# Paid Full: unrestricted.
USAGE_LIMITS: dict[ServiceTier, dict[str, int]] = {
    ServiceTier.TRIAL: {"products": 999, "competitors": 999},
    ServiceTier.FREE: {"products": 50, "competitors": 15},
    ServiceTier.PAID_FULL: {"products": 999, "competitors": 999},
}


def get_service_tier(plan: UserPlan) -> ServiceTier:
    """Map UserPlan to canonical ServiceTier."""
    return PLAN_TO_TIER.get(plan, ServiceTier.FREE)


def is_trial(plan: UserPlan) -> bool:
    """True if plan is Trial tier."""
    return get_service_tier(plan) == ServiceTier.TRIAL


def is_free(plan: UserPlan) -> bool:
    """True if plan is Free tier (restricted)."""
    return get_service_tier(plan) == ServiceTier.FREE


def is_paid(plan: UserPlan) -> bool:
    """True if plan is Paid Full tier."""
    return get_service_tier(plan) == ServiceTier.PAID_FULL


def is_trial_expired(trial_ends_at: datetime | None) -> bool:
    """True if trial has expired. None = no trial, treated as not expired."""
    if trial_ends_at is None:
        return False
    now = datetime.now(timezone.utc)
    return trial_ends_at <= now


def has_feature(plan: UserPlan, feature: Feature) -> bool:
    """Check if plan has access to feature."""
    tier = get_service_tier(plan)
    entitlements = FEATURE_ENTITLEMENTS.get(tier, {})
    return entitlements.get(feature, False)


def get_limit(plan: UserPlan, limit_key: str) -> int:
    """Get usage limit for plan. Keys: products, competitors, etc."""
    tier = get_service_tier(plan)
    limits = USAGE_LIMITS.get(tier, USAGE_LIMITS[ServiceTier.FREE])
    return limits.get(limit_key, 0)


def get_entitlements_for_frontend(
    plan: UserPlan,
    trial_ends_at: datetime | None = None,
) -> dict[str, Any]:
    """Return plan metadata for frontend: tier, features, limits, trial state."""
    tier = get_service_tier(plan)
    features = FEATURE_ENTITLEMENTS.get(tier, {})
    limits = USAGE_LIMITS.get(tier, USAGE_LIMITS[ServiceTier.FREE])
    return {
        "service_tier": tier.value,
        "features": {f.value: features.get(f, False) for f in Feature},
        "limits": limits,
        "trial_duration_days": TRIAL_DURATION_DAYS,
        "is_trial_expired": is_trial_expired(trial_ends_at),
    }
