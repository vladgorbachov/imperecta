import { useQuery } from "@tanstack/react-query";
import type { PoolProductsParams } from "@/api/products";
import { productsApi } from "@/api/products";
import { useDisplayCurrencyStore } from "@/stores/displayCurrencyStore";

export function usePoolProducts(params: PoolProductsParams) {
  const displayCurrency = useDisplayCurrencyStore((state) => state.displayCurrency);
  const requestParams = { ...params, display_currency: displayCurrency };

  return useQuery({
    queryKey: ["pool-products", requestParams],
    queryFn: async () => {
      const { data } = await productsApi.fetchPoolProducts(requestParams);
      return data;
    },
    staleTime: 30_000,
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
