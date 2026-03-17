import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/api/analytics";

export function usePriceHistory(
  productId: string | undefined,
  period: "7d" | "30d" | "90d" = "7d"
) {
  return useQuery({
    queryKey: ["analytics", "price-history", productId, period],
    queryFn: async () => {
      if (!productId) return null;
      const { data } = await analyticsApi.getPriceHistory(productId, period);
      return data;
    },
    enabled: !!productId,
  });
}

export function useComparison(productId: string | undefined) {
  return useQuery({
    queryKey: ["analytics", "comparison", productId],
    queryFn: async () => {
      if (!productId) return null;
      const { data } = await analyticsApi.getComparison(productId);
      return data;
    },
    enabled: !!productId,
  });
}
