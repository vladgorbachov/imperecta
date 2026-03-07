import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/api/analytics";

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: async () => {
      const { data } = await analyticsApi.getDashboardSummary();
      return data;
    },
  });
}

export function useDashboardKpi() {
  return useQuery({
    queryKey: ["dashboard", "kpi"],
    queryFn: async () => {
      const { data } = await analyticsApi.getKpi();
      return data;
    },
  });
}

export function useDashboardAnomalies() {
  return useQuery({
    queryKey: ["dashboard", "anomalies"],
    queryFn: async () => {
      const { data } = await analyticsApi.getDashboardAnomalies();
      return data.items;
    },
  });
}
