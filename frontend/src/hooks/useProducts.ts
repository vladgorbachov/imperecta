import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { productsApi } from "../api/products";

export function useProducts() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["products"],
    queryFn: () => productsApi.list(),
  });
  const createMutation = useMutation({
    mutationFn: productsApi.create,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
  return { products: data?.data, isLoading, createMutation };
}
