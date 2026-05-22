import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as adminApi from "@/api/admin";
import { marketsApi, marketsQueryKeys } from "@/api/markets";

export const useAdminStats = () =>
  useQuery({
    queryKey: ["admin", "stats"],
    queryFn: () => adminApi.getAdminStats().then((r) => r.data),
  });

export const useAdminMarketplaces = () =>
  useQuery({
    queryKey: ["admin", "marketplaces"],
    queryFn: () => adminApi.getAdminMarketplaces().then((r) => r.data),
  });

export const useMarketplaceLogs = (id: string) =>
  useQuery({
    queryKey: ["admin", "marketplace-logs", id],
    queryFn: () => adminApi.getMarketplaceLogs(id).then((r) => r.data),
    enabled: !!id,
  });

export const useScrapeActivity = () =>
  useQuery({
    queryKey: ["admin", "scrape-activity"],
    queryFn: () => adminApi.getScrapeActivity().then((r) => r.data),
  });

export const useErrorDistribution = () =>
  useQuery({
    queryKey: ["admin", "error-distribution"],
    queryFn: () => adminApi.getErrorDistribution().then((r) => r.data),
  });

export const useAdminUsers = () =>
  useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => adminApi.getAdminUsers().then((r) => r.data),
  });

export const useClaudeStatus = () =>
  useQuery({
    queryKey: ["admin", "claude-status"],
    queryFn: () => adminApi.getClaudeStatus().then((r) => r.data),
    refetchInterval: 60_000,
  });

export const useApiHealth = () =>
  useQuery({
    queryKey: ["admin", "api-health"],
    queryFn: () => adminApi.getApiHealth().then((r) => r.data),
    refetchInterval: 60_000,
  });

export const useAddMarketplace = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (url: string) => adminApi.addMarketplace(url).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin"] }),
  });
};

export const useDeleteMarketplace = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminApi.deleteMarketplace(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin"] }),
  });
};

export const useMarketsIngest = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => marketsApi.triggerIngest().then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: marketsQueryKeys.all });
      qc.invalidateQueries({ queryKey: marketsQueryKeys.refreshMetadata() });
    },
  });
};

export const useParsingTestMarketplaces = () =>
  useQuery({
    queryKey: ["admin", "parsing", "test-marketplaces"],
    queryFn: () => adminApi.getParsingTestMarketplaces().then((r) => r.data),
  });

export const useAddParsingTestMarketplaces = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => adminApi.addParsingTestMarketplaces().then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "parsing", "test-marketplaces"] });
    },
  });
};

export const useRunParsingFullTest = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => adminApi.runParsingFullTest().then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "parsing", "test-runs"] });
    },
  });
};

export const useParsingTestRuns = (limit: number) =>
  useQuery({
    queryKey: ["admin", "parsing", "test-runs", limit],
    queryFn: () => adminApi.getParsingTestRuns(limit).then((r) => r.data),
  });

export const useParsingJobStatus = (
  jobId: string | null,
  options?: {
    enabled?: boolean;
    refetchInterval?: number | false;
  },
) =>
  useQuery({
    queryKey: ["admin", "parsing", "job-status", jobId],
    queryFn: () => adminApi.getParsingJobStatus(jobId as string).then((r) => r.data),
    enabled: Boolean(jobId) && (options?.enabled ?? true),
    refetchInterval: options?.refetchInterval,
  });
