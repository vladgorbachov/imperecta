import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { PoolProductsParams } from "@/api/products";
import { productsApi } from "@/api/products";
import { useDisplayCurrencyStore } from "@/stores/displayCurrencyStore";

export function usePoolProducts(
  params: PoolProductsParams,
  options?: { enabled?: boolean },
) {
  const displayCurrency = useDisplayCurrencyStore((state) => state.displayCurrency);
  const requestParams = { ...params, display_currency: displayCurrency };

  return useQuery({
    queryKey: ["pool-products", requestParams],
    queryFn: async () => {
      const { data } = await productsApi.fetchPoolProducts(requestParams);
      return data;
    },
    staleTime: 30_000,
    /* Page flips render instantly over the previous page instead of a
       skeleton — perceived latency win while the next page loads. */
    placeholderData: keepPreviousData,
    enabled: options?.enabled ?? true,
  });
}

export function usePoolCategories() {
  return useQuery({
    queryKey: ["pool-categories"],
    queryFn: async () => {
      const { data } = await productsApi.getPoolCategories();
      return data;
    },
    staleTime: 60_000,
  });
}
