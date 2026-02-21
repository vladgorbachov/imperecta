import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { competitorsApi } from "../api/competitors";

export function useCompetitors(productId?: number) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["competitors", productId],
    queryFn: () => competitorsApi.list(productId),
  });
  const createMutation = useMutation({
    mutationFn: competitorsApi.create,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["competitors"] }),
  });
  return { competitors: data?.data, isLoading, createMutation };
}
