import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  alertsApi,
  type AlertRuleCreatePayload,
} from "@/api/alerts";

const RULES_KEY = ["alerts", "rules"] as const;
const EVENTS_KEY = "alerts-events";

export function useAlertRules() {
  return useQuery({
    queryKey: RULES_KEY,
    queryFn: () => alertsApi.listRules().then((r) => r.data),
    staleTime: 30_000,
  });
}

export function useAlertEvents(params?: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: [EVENTS_KEY, params?.limit ?? 50, params?.offset ?? 0],
    queryFn: () => alertsApi.listEvents(params).then((r) => r.data),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useCreateAlertRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AlertRuleCreatePayload) =>
      alertsApi.createRule(payload).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: RULES_KEY });
    },
  });
}

export function useUpdateAlertRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...payload
    }: { id: string } & Partial<AlertRuleCreatePayload> & { is_active?: boolean }) =>
      alertsApi.updateRule(id, payload).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: RULES_KEY });
    },
  });
}

export function useDeleteAlertRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => alertsApi.deleteRule(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: RULES_KEY });
    },
  });
}
