import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "../api/analytics";

export function useAnalytics(productId: number, period?: string) {
  const { data, isLoading } = useQuery({
    queryKey: ["analytics", productId, period],
    queryFn: () => analyticsApi.priceHistory(productId, period),
    enabled: !!productId,
  });
  return { priceHistory: data?.data, isLoading };
}
