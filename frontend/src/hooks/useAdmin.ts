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
