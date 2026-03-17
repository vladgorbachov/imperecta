import { useQuery } from "@tanstack/react-query";
import type { PoolProductsParams } from "@/api/products";
import { productsApi } from "@/api/products";

export function usePoolProducts(params: PoolProductsParams) {
  return useQuery({
    queryKey: ["pool-products", params],
    queryFn: async () => {
      const { data } = await productsApi.fetchPoolProducts(params);
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
