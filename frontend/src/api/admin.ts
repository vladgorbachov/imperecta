import { apiClient } from "./client";

export interface AdminStats {
  users_count?: number;
  users?: number;
  active_users_count?: number;
  marketplaces_count?: number;
  marketplaces?: number;
  active_marketplaces_count?: number;
  products_in_pool?: number;
  total_scrapes_today?: number;
  successful_scrapes_today?: number;
  failed_scrapes_today?: number;
  error_rate_today?: number;
  total_products_monitored?: number;
  total_competitor_products?: number;
}

export interface AdminMarketplace {
  marketplace_id: string;
  name: string;
  domain: string;
  country: string;
  region: string;
  source: "registry" | "admin";
  is_active: boolean;
  last_scrape_at: string | null;
  last_scrape_status: "success" | "error" | "timeout" | "blocked" | null;
  last_error: string | null;
  total_scrapes: number;
  successful_scrapes: number;
  failed_scrapes: number;
  success_rate: number;
  products_count: number;
}

export interface ScrapeLog {
  id: number;
  url: string;
  status: string;
  error_message: string | null;
  price_found: number | null;
  duration_ms: number | null;
  proxy_used: boolean;
  created_at: string;
}

export interface ScrapeActivity {
  labels: string[];
  datasets: { label: string; data: number[] }[];
}

export interface ErrorDistribution {
  labels: string[];
  data: number[];
}

export interface AdminUser {
  id: string;
  email: string;
  name?: string;
  plan: string;
  products_count?: number;
  created_at: string;
  last_login_at: string | null;
  is_active?: boolean;
}

export const getAdminStats = () => apiClient.get<AdminStats>("/admin/stats");
export const getAdminMarketplaces = () =>
  apiClient.get<AdminMarketplace[]>("/admin/marketplaces");
export const getMarketplaceLogs = (id: string) =>
  apiClient.get<ScrapeLog[]>(`/admin/marketplaces/${id}/logs`);
export const addMarketplace = (url: string) =>
  apiClient.post<AdminMarketplace>("/admin/marketplaces", { url });
export const updateMarketplace = (
  id: string,
  payload: { name?: string; url?: string; is_active?: boolean },
) => apiClient.patch<AdminMarketplace>(`/admin/marketplaces/${id}`, payload);
export const deleteMarketplace = (id: string) =>
  apiClient.delete(`/admin/marketplaces/${id}`);

export interface ClaudeHealth {
  status:
    | "online"
    | "error"
    | "timeout"
    | "rate_limited"
    | "overloaded"
    | "auth_error"
    | "not_configured";
  message: string;
  latency_ms: number;
  status_code?: number;
}

export interface ClaudeStats {
  calls_24h: number;
  successful_24h: number;
  failed_24h: number;
  avg_latency_ms: number;
  total_tokens_24h: number;
  last_success_at: string | null;
  last_error: string | null;
  last_error_at: string | null;
}

export interface ClaudeStatus {
  health?: ClaudeHealth;
  stats?: ClaudeStats;
  configured?: boolean;
  model?: string;
}

export const getClaudeStatus = () =>
  apiClient.get<ClaudeStatus>("/admin/claude-status");

export const recalculateQuotas = () =>
  apiClient.post<RecalculateQuotasResponse>("/admin/marketplaces/recalculate-quotas");

export const clearPool = () =>
  apiClient.post<{ deleted: number; message: string }>("/admin/products/clear-pool");


export interface PoolDiagnostics {
  marketplaces: { total: number; active: number; zero_quota: number };
  global_products: { total: number; by_status: Record<string, number> };
  price_snapshots: number;
  discovery_logs: {
    total: number;
    recent: Array<{
      domain: string;
      status: string;
      found: number;
      new: number;
      errors: number;
      error: string | null;
      started_at: string | null;
      duration_s: number | null;
    }>;
  };
  user_products: number;
  marketplace_details: Array<{
    domain: string;
    quota: number;
    products: number;
    active: boolean;
    requires_js: boolean;
    last_discovery: string | null;
  }>;
  diagnosis: string[];
}

export interface RecalculateQuotasResponse {
  status: string;
  active_marketplaces: number;
  quota_per_marketplace: number;
  total_pool_capacity: number;
}

export interface ParsingTestMarketplace {
  id?: string;
  marketplace_code?: string;
  name: string;
  url: string;
  domain?: string;
  is_active?: boolean;
  products_in_pool: number;
  last_successful_scrape: string | null;
  success_rate: number;
  last_run: string | null;
  status: "running" | "completed" | "failed";
}

export interface ParsingMarketplacesDetailedPage {
  items: ParsingDetailedMarketplace[];
  total: number;
  page: number;
  page_size: number;
}

export interface ParsingRunCreateResponse {
  job_id: string;
  started_at: string;
}

export interface ParsingPipelineRun {
  job_id: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  current_stage: string | null;
  marketplace_codes: string[] | null;
  listings_created: number;
  prices_saved: number;
  errors_count: number;
  status: "running" | "completed" | "failed";
  error_message: string | null;
  summary_pending: boolean;
}

/** @deprecated Use ParsingPipelineRun */
export type ParsingTestRun = ParsingPipelineRun;

export interface ParsingMarketplaceBreakdown {
  marketplace_id: string;
  domain: string;
  listings_created: number;
  prices_saved: number;
  errors_count: number;
  duration_ms: number;
  status: "running" | "completed" | "failed";
}

export interface ParsingJobMetadata {
  current_stage?: string;
  last_activity_at?: string | null;
  marketplace_codes?: string[];
  discovery_marketplace_done?: number;
  discovery_marketplace_total?: number;
  discovery_current_domain?: string | null;
  timings?: {
    discovery_ms: number;
    scrape_ms: number;
    persist_ms: number;
    total_ms: number;
  };
  summary?: {
    listings_created: number;
    prices_saved: number;
    errors_count: number;
  };
  per_marketplace?: ParsingMarketplaceBreakdown[];
  discovery_errors?: string[];
  celery_task_id?: string;
  worker_log_tail?: string[];
  error?: string;
}

export interface ParsingWorkerLogRelayLine {
  seq: number;
  at: string | null;
  line: string;
  job_id: string | null;
}

export interface ParsingWorkerLogRelayResponse {
  lines: ParsingWorkerLogRelayLine[];
  next_cursor: number;
  total_buffered: number;
  visible_lines: number;
}

export interface ParsingDiscoveryProgress {
  done: number;
  total: number;
  current_domain: string | null;
}

export interface ParsingJobStatus {
  job_id: string;
  status: "running" | "completed" | "failed";
  current_stage: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  metadata: ParsingJobMetadata | null;
  discovery: ParsingDiscoveryProgress | null;
}

export interface ParsingDetailedUser {
  id: string;
  email: string;
  name: string | null;
  company_name?: string | null;
  plan: string;
  is_active: boolean;
  is_superuser: boolean;
  language: string;
  timezone: string;
  login_count: number;
  tracked_products: number;
  last_login_at: string | null;
  created_at: string | null;
}

export interface ParsingDetailedMarketplace {
  id: string;
  marketplace_code: string;
  name: string;
  domain: string;
  base_url: string;
  country_code: string;
  currency_code: string;
  scraper_type: string;
  requires_js: boolean;
  is_active: boolean;
  product_quota: number;
  products_in_pool: number;
  active_listings: number;
  rate_limit_delay: number;
  last_discovery_at: string | null;
  last_discovery_status: string | null;
  last_discovery_products_found: number;
  last_scrape_at: string | null;
  last_scrape_status: string | null;
  last_log_at: string | null;
  total_runs: number;
  success_runs: number;
  error_runs: number;
  success_rate: number;
  last_error_message: string | null;
}

export interface ParsingLiveStep {
  event_id: number;
  event_type: "listing_scrape";
  created_at: string | null;
  status: string;
  listing_id: string;
  marketplace_id: string;
  marketplace_domain: string | null;
  url: string;
  price_found: number | null;
  in_stock_found: boolean | null;
  duration_ms: number | null;
  scraper_type: string | null;
  error_category: string | null;
  error_message: string | null;
}

export interface ParsingJobLiveFeed {
  job_id: string;
  status: "running" | "completed" | "failed";
  current_stage: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  total_steps: number;
  status_counts: Record<string, number>;
  summary: {
    listings_created: number;
    prices_saved: number;
    errors_count: number;
  };
  timings: {
    discovery_ms: number;
    scrape_ms: number;
    persist_ms: number;
    total_ms: number;
  };
  estimated_total_steps: number | null;
  estimated_remaining_seconds: number | null;
  warning_flags: string[];
  steps: ParsingLiveStep[];
  paging: {
    limit: number;
    offset: number;
    total: number;
    has_more: boolean;
  };
}

export interface ParsingActiveJobResponse {
  active_job: {
    job_id: string;
    status: "running" | "completed" | "failed";
    current_stage: string | null;
    started_at: string | null;
    metadata: ParsingJobMetadata | null;
  } | null;
}

export interface AdminUserCreatePayload {
  email: string;
  password: string;
  name?: string | null;
  company_name?: string | null;
  plan: string;
  language: string;
  timezone?: string | null;
  is_active: boolean;
  is_superuser: boolean;
}

export interface AdminUserUpdatePayload {
  email?: string;
  name?: string | null;
  company_name?: string | null;
  plan?: string;
  language?: string;
  timezone?: string | null;
  is_active?: boolean;
  is_superuser?: boolean;
}

export interface AdminUserStatusPayload {
  is_active: boolean;
}

export interface AdminUserRolePayload {
  is_superuser: boolean;
}

export interface AdminUserResetPasswordPayload {
  new_password: string;
  force_password_change: boolean;
}

export const getParsingTestMarketplaces = () =>
  apiClient.get<ParsingTestMarketplace[]>("/admin/parsing/test-marketplaces");

export interface RunPipelinePayload {
  marketplace_codes?: string[];
}

export const runParsingPipeline = (payload?: RunPipelinePayload) =>
  apiClient.post<ParsingRunCreateResponse>("/admin/parsing/run-pipeline", payload ?? {});

/** Full pool run (all active marketplaces). */
export const runParsingFullCollection = () => runParsingPipeline();

/** @deprecated Use runParsingPipeline */
export const runParsingFullTest = runParsingFullCollection;

export const getParsingPipelineRuns = (limit = 50) =>
  apiClient.get<ParsingPipelineRun[]>("/admin/parsing/pipeline-runs", { params: { limit } });

/** @deprecated Use getParsingPipelineRuns */
export const getParsingTestRuns = getParsingPipelineRuns;

export const cancelParsingActiveJob = () =>
  apiClient.post<{ job_id: string; status: string; cancelled: boolean }>(
    "/admin/parsing/cancel-active-job",
  );

export const getParsingJobStatus = (jobId: string) =>
  apiClient.get<ParsingJobStatus>(`/admin/parsing/job-status/${jobId}`);

export const getParsingUsersDetailed = (limit = 500) =>
  apiClient.get<ParsingDetailedUser[]>("/admin/parsing/users-detailed", { params: { limit } });

export const createAdminUser = (payload: AdminUserCreatePayload) =>
  apiClient.post<ParsingDetailedUser>("/admin/parsing/users", payload);

export const updateAdminUser = (userId: string, payload: AdminUserUpdatePayload) =>
  apiClient.patch<ParsingDetailedUser>(`/admin/parsing/users/${userId}`, payload);

export const setAdminUserStatus = (userId: string, payload: AdminUserStatusPayload) =>
  apiClient.patch<ParsingDetailedUser>(`/admin/parsing/users/${userId}/status`, payload);

export const setAdminUserRole = (userId: string, payload: AdminUserRolePayload) =>
  apiClient.patch<ParsingDetailedUser>(`/admin/parsing/users/${userId}/role`, payload);

export const resetAdminUserPassword = (
  userId: string,
  payload: AdminUserResetPasswordPayload,
) => apiClient.post<ParsingDetailedUser>(`/admin/parsing/users/${userId}/reset-password`, payload);

export const deleteAdminUser = (userId: string) =>
  apiClient.delete<{ deleted: boolean }>(`/admin/parsing/users/${userId}`);

export const getParsingMarketplacesDetailed = (page = 1, pageSize = 20) =>
  apiClient.get<ParsingMarketplacesDetailedPage>("/admin/parsing/marketplaces-detailed", {
    params: { page, page_size: pageSize },
  });

export const getParsingJobLiveFeed = (jobId: string, limit = 200, offset = 0) =>
  apiClient.get<ParsingJobLiveFeed>(`/admin/parsing/job-live-feed/${jobId}`, {
    params: { limit, offset },
  });

export const getParsingWorkerLogRelay = (
  after: number,
  jobId?: string | null,
  limit = 50,
) =>
  apiClient.get<ParsingWorkerLogRelayResponse>("/admin/parsing/worker-log-relay", {
    params: {
      after,
      limit,
      ...(jobId ? { job_id: jobId } : {}),
    },
  });

export const getParsingActiveJob = () =>
  apiClient.get<ParsingActiveJobResponse>("/admin/parsing/active-job");
