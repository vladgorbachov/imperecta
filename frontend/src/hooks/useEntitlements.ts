/**
 * Plan entitlements from backend. Single source of truth for feature access.
 * Uses entitlements from GET /users/me when available.
 */

import { useAuthStore } from "@/stores/authStore";

export type ServiceTier = "trial" | "free" | "paid_full";

export const FEATURE_AI_ANALYST = "ai_analyst";

export function useEntitlements() {
  const user = useAuthStore((s) => s.user);
  const ent = user?.entitlements;

  const serviceTier = (ent?.service_tier as ServiceTier | undefined) ?? null;

  const hasFeature = (feature: string): boolean => {
    if (feature === FEATURE_AI_ANALYST) {
      return serviceTier === "paid_full";
    }
    const features = ent?.features;
    if (!features || typeof features !== "object") return false;
    const desc = Object.getOwnPropertyDescriptor(features, feature);
    return desc?.value === true;
  };

  const hasAiAnalyst = hasFeature(FEATURE_AI_ANALYST);
  const isTrial = serviceTier === "trial";
  const isFree = serviceTier === "free";
  const isPaidFull = serviceTier === "paid_full";
  const isTrialExpired = ent?.is_trial_expired ?? false;
  const trialDurationDays = ent?.trial_duration_days ?? 0;

  return {
    serviceTier,
    hasFeature,
    hasAiAnalyst,
    isTrial,
    isFree,
    isPaidFull,
    isTrialExpired,
    trialDurationDays,
    limits: ent?.limits ?? null,
  };
}
