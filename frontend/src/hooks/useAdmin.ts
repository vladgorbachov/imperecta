import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as adminApi from "@/api/admin";
import { marketsApi, marketsQueryKeys } from "@/api/markets";

export const useAdminStats = () =>
  useQuery({
    queryKey: ["admin", "stats"],
    queryFn: () => adminApi.getAdminStats().then((r) => r.data),
  });

export const useClaudeStatus = () =>
  useQuery({
    queryKey: ["admin", "claude-status"],
    queryFn: () => adminApi.getClaudeStatus().then((r) => r.data),
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

export const useParsingUsersDetailed = (limit = 500) =>
  useQuery({
    queryKey: ["admin", "parsing", "users-detailed", limit],
    queryFn: () => adminApi.getParsingUsersDetailed(limit).then((r) => r.data),
  });

export const useParsingMarketplacesDetailed = (limit = 1000) =>
  useQuery({
    queryKey: ["admin", "parsing", "marketplaces-detailed", limit],
    queryFn: () => adminApi.getParsingMarketplacesDetailed(limit).then((r) => r.data),
  });

export const useParsingJobLiveFeed = (
  jobId: string | null,
  options?: {
    enabled?: boolean;
    refetchInterval?: number | false;
    limit?: number;
    offset?: number;
  },
) =>
  useQuery({
    queryKey: [
      "admin",
      "parsing",
      "job-live-feed",
      jobId,
      options?.limit ?? 200,
      options?.offset ?? 0,
    ],
    queryFn: () =>
      adminApi
        .getParsingJobLiveFeed(jobId as string, options?.limit ?? 200, options?.offset ?? 0)
        .then((r) => r.data),
    enabled: Boolean(jobId) && (options?.enabled ?? true),
    refetchInterval: options?.refetchInterval,
  });

export const useParsingActiveJob = (refetchInterval: number | false = 5000) =>
  useQuery({
    queryKey: ["admin", "parsing", "active-job"],
    queryFn: () => adminApi.getParsingActiveJob().then((r) => r.data),
    refetchInterval,
  });
