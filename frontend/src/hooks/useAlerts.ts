import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { alertsApi } from "../api/alerts";

export function useAlerts() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["alerts"],
    queryFn: () => alertsApi.list(),
  });
  const createMutation = useMutation({
    mutationFn: alertsApi.create,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });
  return { alerts: data?.data, isLoading, createMutation };
}
