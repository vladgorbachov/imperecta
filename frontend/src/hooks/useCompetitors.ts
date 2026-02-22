import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { competitorsApi } from "../api/competitors";

export function useCompetitors() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["competitors"],
    queryFn: () => competitorsApi.list(),
  });
  const createMutation = useMutation({
    mutationFn: competitorsApi.create,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["competitors"] }),
  });
  return { competitors: data?.data ?? [], isLoading, createMutation };
}
