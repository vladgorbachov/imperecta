/**
 * Plan limits for products. Reads live usage from /entitlements/usage and
 * compares against the limit returned by that same endpoint (single source of
 * truth - no hardcoded 50). Free-tier enforcement: `used >= limit` blocks
 * further adds. Trial and Paid Full have practically unlimited limits.
 */

import { useQuery } from "@tanstack/react-query";
import { entitlementsApi, entitlementsQueryKeys } from "@/api/entitlements";
import { useEntitlements } from "@/hooks/useEntitlements";

export function usePlanLimits() {
  const { serviceTier } = useEntitlements();
  const { data: usage } = useQuery({
    queryKey: entitlementsQueryKeys.usage(),
    queryFn: () => entitlementsApi.getUsage().then((r) => r.data),
  });

  const totalProducts = usage?.products.used ?? 0;
  const productLimit = usage?.products.limit ?? 0;
  const hasProductLimit = serviceTier === "free";
  const canAddProducts = !hasProductLimit || (productLimit > 0 && totalProducts < productLimit);
  const isAtOrOverProductLimit = hasProductLimit && productLimit > 0 && totalProducts >= productLimit;

  return {
    plan: serviceTier,
    totalProducts,
    productLimit,
    hasProductLimit,
    canAddProducts,
    isAtOrOverProductLimit,
  };
}
