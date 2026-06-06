import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/api/analytics";
import { useDisplayCurrencyStore } from "@/stores/displayCurrencyStore";

export function usePriceHistory(
  productId: string | undefined,
  period: "7d" | "30d" | "90d" = "7d"
) {
  const displayCurrency = useDisplayCurrencyStore((state) => state.displayCurrency);

  return useQuery({
    queryKey: ["analytics", "price-history", productId, period, displayCurrency],
    queryFn: async () => {
      if (!productId) return null;
      const { data } = await analyticsApi.getPriceHistory(productId, period, displayCurrency);
      return data;
    },
    enabled: !!productId,
  });
}

export function useComparison(productId: string | undefined) {
  const displayCurrency = useDisplayCurrencyStore((state) => state.displayCurrency);

  return useQuery({
    queryKey: ["analytics", "comparison", productId, displayCurrency],
    queryFn: async () => {
      if (!productId) return null;
      const { data } = await analyticsApi.getComparison(productId, displayCurrency);
      return data;
    },
    enabled: !!productId,
  });
}
