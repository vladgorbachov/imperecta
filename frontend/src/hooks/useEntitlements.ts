/**
 * Plan entitlements from backend. Single source of truth for feature access.
 * Uses entitlements from GET /auth/me when available.
 */

import { useAuthStore } from "@/stores/authStore";

export type ServiceTier = "trial" | "free" | "paid_full";

export const FEATURE_AI_ANALYST = "ai_analyst";

export function useEntitlements() {
  const user = useAuthStore((s) => s.user);
  const ent = user?.entitlements;

  const serviceTier: ServiceTier =
    (ent?.service_tier as ServiceTier) ??
    (user?.plan === "trial" ? "trial" : user?.plan === "starter" ? "free" : "paid_full");

  const hasFeature = (feature: string): boolean => {
    if (ent?.features && feature in ent.features) {
      return ent.features[feature] === true;
    }
    if (feature === FEATURE_AI_ANALYST) {
      return serviceTier === "paid_full";
    }
    return false;
  };

  const getLimit = (key: string): number => {
    return ent?.limits?.[key] ?? 999;
  };

  const hasAiAnalyst = hasFeature(FEATURE_AI_ANALYST);
  const isTrial = serviceTier === "trial";
  const isFree = serviceTier === "free";
  const isPaidFull = serviceTier === "paid_full";
  const isTrialExpired = ent?.is_trial_expired ?? false;
  const trialDurationDays = ent?.trial_duration_days ?? 14;

  return {
    serviceTier,
    hasFeature,
    getLimit,
    hasAiAnalyst,
    isTrial,
    isFree,
    isPaidFull,
    isTrialExpired,
    trialDurationDays,
    limits: ent?.limits ?? { products: 50, competitors: 15 },
  };
}
