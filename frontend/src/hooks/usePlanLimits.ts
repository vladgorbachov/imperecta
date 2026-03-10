/**
 * Plan limits for products. Uses entitlements when available.
 * Free tier has 50 product limit; Trial and Paid Full have full access.
 */

import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/api/analytics";
import { useEntitlements } from "@/hooks/useEntitlements";

export function usePlanLimits() {
  const { serviceTier, getLimit } = useEntitlements();
  const { data: summary } = useQuery({
    queryKey: ["analytics", "dashboard", "summary"],
    queryFn: () => analyticsApi.getDashboardSummary().then((r) => r.data),
  });

  const totalProducts = summary?.total_products ?? 0;
  const productLimit = getLimit("products");
  const hasProductLimit = serviceTier === "free";
  const canAddProducts = !hasProductLimit || totalProducts < productLimit;
  const isAtOrOverProductLimit = hasProductLimit && totalProducts >= productLimit;

  return {
    plan: serviceTier,
    totalProducts,
    productLimit,
    hasProductLimit,
    canAddProducts,
    isAtOrOverProductLimit,
  };
}
