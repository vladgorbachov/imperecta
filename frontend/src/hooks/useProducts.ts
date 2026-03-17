import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { productsApi } from "@/api/products";

interface UseProductsParams {
  search?: string;
  category?: string;
  sort?: string;
  page?: number;
  limit?: number;
}

export function useProducts(params: UseProductsParams = {}) {
  const { search, category, sort, page = 1, limit = 20 } = params;
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["products", search, category, sort, page, limit],
    queryFn: async () => {
      const { data: res } = await productsApi.list({
        search: search || undefined,
        category: category || undefined,
        sort: sort || undefined,
        page,
        limit,
      });
      return res;
    },
  });

  const createMutation = useMutation({
    mutationFn: productsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: productsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });

  return {
    products: data?.items ?? [],
    total: data?.total ?? 0,
    isLoading,
    createMutation,
    deleteMutation,
  };
}

export function useProduct(id: string | undefined) {
  return useQuery({
    queryKey: ["products", id],
    queryFn: async () => {
      if (!id) return null;
      const { data } = await productsApi.get(id);
      return data;
    },
    enabled: !!id,
  });
}

export function useProductCategories() {
  return useQuery({
    queryKey: ["products", "categories"],
    queryFn: async () => {
      const { data } = await productsApi.getCategories();
      return data;
    },
  });
}
