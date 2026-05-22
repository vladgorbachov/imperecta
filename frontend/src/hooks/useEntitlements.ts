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

  const KNOWN_LIMIT_KEYS = ["products", "competitors"] as const;
  const getLimit = (key: string): number => {
    if (!KNOWN_LIMIT_KEYS.includes(key as (typeof KNOWN_LIMIT_KEYS)[number])) return 0;
    const limits = ent?.limits;
    if (!limits || typeof limits !== "object") return 0;
    const desc = Object.getOwnPropertyDescriptor(limits, key);
    const val = desc?.value;
    return typeof val === "number" ? val : 0;
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
    getLimit,
    hasAiAnalyst,
    isTrial,
    isFree,
    isPaidFull,
    isTrialExpired,
    trialDurationDays,
    limits: ent?.limits ?? null,
  };
}
