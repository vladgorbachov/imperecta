import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
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

export const useCountries = () =>
  useQuery({
    queryKey: ["admin", "countries"],
    queryFn: () => adminApi.getCountries().then((r) => r.data),
    staleTime: 60 * 60 * 1000,
  });

export const useAddMarketplace = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { url: string; country_code: string }) =>
      adminApi.addMarketplace(payload).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin"] }),
  });
};

export const useUpdateMarketplace = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: {
        name?: string;
        url?: string;
        is_active?: boolean;
        country_code?: string;
      };
    }) => adminApi.updateMarketplace(id, payload).then((r) => r.data),
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
    },
  });
};

export const useParsingTestMarketplaces = () =>
  useQuery({
    queryKey: ["admin", "parsing", "test-marketplaces"],
    queryFn: () => adminApi.getParsingTestMarketplaces().then((r) => r.data),
  });

export const useRunParsingPipeline = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload?: adminApi.RunPipelinePayload) =>
      adminApi.runParsingPipeline(payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "parsing", "pipeline-runs"] });
      qc.invalidateQueries({ queryKey: ["admin", "parsing", "active-job"] });
    },
  });
};

export const useCancelParsingActiveJob = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => adminApi.cancelParsingActiveJob().then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "parsing", "pipeline-runs"] });
      qc.invalidateQueries({ queryKey: ["admin", "parsing", "active-job"] });
    },
  });
};

export const useParsingPipelineRuns = (limit: number) =>
  useQuery({
    queryKey: ["admin", "parsing", "pipeline-runs", limit],
    queryFn: () => adminApi.getParsingPipelineRuns(limit).then((r) => r.data),
    refetchInterval: 5000,
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

export const useCreateAdminUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: adminApi.AdminUserCreatePayload) =>
      adminApi.createAdminUser(payload).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "parsing", "users-detailed"] }),
  });
};

export const useUpdateAdminUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, payload }: { userId: string; payload: adminApi.AdminUserUpdatePayload }) =>
      adminApi.updateAdminUser(userId, payload).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "parsing", "users-detailed"] }),
  });
};

export const useSetAdminUserStatus = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, is_active }: { userId: string; is_active: boolean }) =>
      adminApi.setAdminUserStatus(userId, { is_active }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "parsing", "users-detailed"] }),
  });
};

export const useSetAdminUserRole = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, is_superuser }: { userId: string; is_superuser: boolean }) =>
      adminApi.setAdminUserRole(userId, { is_superuser }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "parsing", "users-detailed"] }),
  });
};

export const useResetAdminUserPassword = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      userId,
      new_password,
      force_password_change,
    }: {
      userId: string;
      new_password: string;
      force_password_change: boolean;
    }) =>
      adminApi
        .resetAdminUserPassword(userId, { new_password, force_password_change })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "parsing", "users-detailed"] }),
  });
};

export const useDeleteAdminUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => adminApi.deleteAdminUser(userId).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "parsing", "users-detailed"] }),
  });
};

export const useParsingMarketplacesDetailed = (page = 1, pageSize = 20) =>
  useQuery({
    queryKey: ["admin", "parsing", "marketplaces-detailed", page, pageSize],
    queryFn: () => adminApi.getParsingMarketplacesDetailed(page, pageSize).then((r) => r.data),
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

export const useParsingWorkerLogRelay = (
  after: number,
  jobId: string | null,
  options?: {
    enabled?: boolean;
    refetchInterval?: number | false;
  },
) =>
  useQuery({
    queryKey: ["admin", "parsing", "worker-log-relay", jobId, after],
    queryFn: () =>
      adminApi.getParsingWorkerLogRelay(after, jobId, 50).then((r) => r.data),
    enabled: options?.enabled ?? true,
    refetchInterval: options?.refetchInterval,
    staleTime: 0,
  });

export const useParsingActiveJob = (refetchInterval: number | false = 5000) =>
  useQuery({
    queryKey: ["admin", "parsing", "active-job"],
    queryFn: () => adminApi.getParsingActiveJob().then((r) => r.data),
    refetchInterval,
  });

export const useServiceAlerts = (params: adminApi.ServiceAlertsParams) =>
  useQuery({
    queryKey: [
      "admin",
      "service_alerts",
      params.module ?? null,
      params.submodule ?? null,
      params.severity ?? null,
      params.resolved ?? "all",
      params.limit ?? 50,
      params.offset ?? 0,
    ],
    queryFn: () => adminApi.getServiceAlerts(params).then((r) => r.data),
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });

export const useResolveServiceAlert = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminApi.resolveServiceAlert(id).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "service_alerts"] });
    },
  });
};

// --- Compliance: blocked countries (F1) ---

const BLOCKED_COUNTRIES_KEY = ["admin", "blocked-countries"] as const;

export const useBlockedCountries = () =>
  useQuery({
    queryKey: BLOCKED_COUNTRIES_KEY,
    queryFn: () => adminApi.getBlockedCountries().then((r) => r.data),
    staleTime: 30_000,
  });

export const useAvailableCountries = (enabled = true) =>
  useQuery({
    queryKey: [...BLOCKED_COUNTRIES_KEY, "available"],
    queryFn: () => adminApi.getAvailableCountries().then((r) => r.data),
    staleTime: 60 * 60 * 1000,
    enabled,
  });

export const useAddBlockedCountry = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: adminApi.BlockedCountryCreatePayload) =>
      adminApi.addBlockedCountry(payload).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin"] }),
  });
};

/** Impact preview — no invalidation, the server writes nothing. */
export const useDryRunBlockedCountry = () =>
  useMutation({
    mutationFn: (payload: Omit<adminApi.BlockedCountryCreatePayload, "dry_run">) =>
      adminApi.dryRunBlockedCountry(payload).then((r) => r.data),
  });

export const useUpdateBlockedCountry = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      code,
      payload,
    }: {
      code: string;
      payload: adminApi.BlockedCountryUpdatePayload;
    }) => adminApi.updateBlockedCountry(code, payload).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin"] }),
  });
};

export const useRemoveBlockedCountry = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => adminApi.removeBlockedCountry(code),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin"] }),
  });
};

export const useCompleteReview = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (note?: string) =>
      adminApi.completeBlockedCountriesReview(note).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin"] }),
  });
};

export const useBlockedCountriesAudit = (cursor: string | null, enabled: boolean) =>
  useQuery({
    queryKey: [...BLOCKED_COUNTRIES_KEY, "audit", cursor],
    queryFn: () => adminApi.getBlockedCountriesAudit({ limit: 50, cursor }).then((r) => r.data),
    enabled,
    placeholderData: keepPreviousData,
  });

export const useCheckIpCountry = () =>
  useMutation({
    mutationFn: (ip: string) => adminApi.checkIpCountry(ip).then((r) => r.data),
  });
