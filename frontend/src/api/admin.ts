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

/**
 * Marketplace mutation result shape from /admin/marketplaces (POST/PATCH).
 * Real scrape statistics live on /admin/parsing/marketplaces-detailed.
 * MP1 dropped the fabricated zero fields (total_scrapes/success_rate/...).
 */
export interface AdminMarketplace {
  marketplace_id: string;
  name: string;
  domain: string;
  country_code: string;
  country: string;
  region: string;
  source: "registry" | "admin";
  is_active: boolean;
  last_scrape_at: string | null;
  last_scrape_status: "success" | "error" | "timeout" | "blocked" | null;
  products_count: number;
}

export interface AdminCountryRef {
  code: string;
  name: string;
  name_local: string | null;
  region: string;
  currency_code: string;
}

export const getAdminStats = () => apiClient.get<AdminStats>("/admin/stats");

export const getCountries = () =>
  apiClient.get<AdminCountryRef[]>("/admin/marketplaces/countries");

export const addMarketplace = (payload: { url: string; country_code: string }) =>
  apiClient.post<AdminMarketplace>("/admin/marketplaces", payload);

export const updateMarketplace = (
  id: string,
  payload: { name?: string; url?: string; is_active?: boolean; country_code?: string },
) => apiClient.patch<AdminMarketplace>(`/admin/marketplaces/${id}`, payload);
export const deleteMarketplace = (id: string) =>
  apiClient.delete(`/admin/marketplaces/${id}`);

/**
 * Backend /admin/claude-status response shape (canonical).
 * Trimmed in FE1 to match the actual backend response (configured, model,
 * model_config); the prior ClaudeHealth/ClaudeStats fields were never emitted
 * by the backend.
 */
export interface ClaudeStatus {
  configured: boolean;
  model: string;
  model_config: string;
}

export const getClaudeStatus = () =>
  apiClient.get<ClaudeStatus>("/admin/claude-status");

/** Pool scrape result shape from /admin/scrape/test-single and diagnostics sample_result. */
export interface ScrapePoolResult {
  success: boolean;
  url: string;
  error: string | null;
  fetch_backend: string | null;
  duration_ms: number | null;
  is_partial: boolean;
  is_empty: boolean;
  extracted_fields: string[];
  missing_fields: string[];
  log_status: string | null;
  data: Record<string, unknown> | null;
}

/** Response from GET /admin/scrape-diagnostics. */
export interface ScrapeDiagnostics {
  total_listings: number;
  with_price_last_24h: number;
  last_5_logs: Array<{
    status: string;
    url: string;
    price_found: number | null;
    duration_ms: number | null;
  }>;
  proxy_provider_status: {
    enabled: boolean;
    healthy: boolean;
  };
  sample_result: ScrapePoolResult | null;
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

/** Top-level pipeline job status returned by /active-job, /job-status, run history, and live feed. */
export type ParsingPipelineJobStatus =
  | "running"
  | "completed"
  | "partial"
  | "failed"
  | "cancelled";

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
  status: ParsingPipelineJobStatus;
  error_message: string | null;
  summary_pending: boolean;
}

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
  status: ParsingPipelineJobStatus;
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
  status: ParsingPipelineJobStatus;
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
    status: ParsingPipelineJobStatus;
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

export const getParsingPipelineRuns = (limit = 50) =>
  apiClient.get<ParsingPipelineRun[]>("/admin/parsing/pipeline-runs", { params: { limit } });

export const cancelParsingActiveJob = () =>
  apiClient.post<{ job_id: string; status: string; cancelled: boolean }>(
    "/admin/parsing/cancel-active-job",
  );

export const getParsingJobStatus = (jobId: string) =>
  apiClient.get<ParsingJobStatus>(`/admin/parsing/job-status/${jobId}`);

export const getParsingUsersDetailed = (limit = 500) =>
  apiClient.get<ParsingDetailedUser[]>("/admin/users", { params: { limit } });

export const createAdminUser = (payload: AdminUserCreatePayload) =>
  apiClient.post<ParsingDetailedUser>("/admin/users", payload);

export const updateAdminUser = (userId: string, payload: AdminUserUpdatePayload) =>
  apiClient.patch<ParsingDetailedUser>(`/admin/users/${userId}`, payload);

export const setAdminUserStatus = (userId: string, payload: AdminUserStatusPayload) =>
  apiClient.patch<ParsingDetailedUser>(`/admin/users/${userId}/status`, payload);

export const setAdminUserRole = (userId: string, payload: AdminUserRolePayload) =>
  apiClient.patch<ParsingDetailedUser>(`/admin/users/${userId}/role`, payload);

export const resetAdminUserPassword = (
  userId: string,
  payload: AdminUserResetPasswordPayload,
) => apiClient.post<ParsingDetailedUser>(`/admin/users/${userId}/reset-password`, payload);

export const deleteAdminUser = (userId: string) =>
  apiClient.delete<{ deleted: boolean }>(`/admin/users/${userId}`);

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

export type ServiceAlertSeverity = "info" | "warning" | "error" | "critical";

export type ServiceAlertResolvedFilter = "open" | "resolved" | "all";

export interface ServiceAlert {
  id: string;
  alert_class: string;
  module: string;
  submodule: string;
  severity: ServiceAlertSeverity;
  anomaly_type: string;
  message: string;
  context: Record<string, unknown> | null;
  triggered_at: string;
  resolved_at: string | null;
}

export interface ServiceAlertsPage {
  items: ServiceAlert[];
  total: number;
  limit: number;
  offset: number;
}

export interface ServiceAlertsParams {
  module?: string;
  submodule?: string;
  severity?: string;
  resolved?: ServiceAlertResolvedFilter;
  limit?: number;
  offset?: number;
}

/** Resolve one service alert (P9 — backend contract in docs/FRONTEND_BACKEND_REQUESTS.md). */
export const resolveServiceAlert = (id: string) =>
  apiClient.patch<ServiceAlert>(`/admin/service_alerts/${id}`, { resolved: true });

export const getServiceAlerts = (params?: ServiceAlertsParams) =>
  apiClient.get<ServiceAlertsPage>("/admin/service_alerts", {
    params: {
      resolved: params?.resolved ?? "all",
      limit: params?.limit ?? 50,
      offset: params?.offset ?? 0,
      ...(params?.module ? { module: params.module } : {}),
      ...(params?.submodule ? { submodule: params.submodule } : {}),
      ...(params?.severity ? { severity: params.severity } : {}),
    },
  });

// --- Compliance: blocked (sanctioned) countries (F1, LEGAL_CLEANUP_PLAN §6.6) ---

export type BlockedReason =
  | "product_exclusion"
  | "comprehensive_sanctions"
  | "restrictive_measures"
  | "other";

export interface BlockedCountryActor {
  id: string;
  email: string;
}

export interface BlockedCountry {
  country_code: string;
  name: string;
  reason: BlockedReason;
  basis: string;
  note: string | null;
  is_active: boolean;
  added_by: BlockedCountryActor | null;
  added_at: string;
  updated_at: string;
  review_due_at: string;
  is_protected: boolean;
  affected_users: number;
  affected_marketplaces: number;
}

export interface BlockedCountriesResponse {
  items: BlockedCountry[];
  last_reviewed_at: string | null;
  next_review_due_at: string;
}

export interface AvailableCountry {
  code: string;
  name: string;
  in_dim_country: boolean;
  is_blocked: boolean;
  is_protected: boolean;
}

export interface BlockedCountryCreatePayload {
  country_code: string;
  reason: BlockedReason;
  basis: string;
  note?: string | null;
  force?: boolean;
  dry_run?: boolean;
}

/** `dry_run: true` answers 200 with the impact counts only. */
export interface BlockedCountryDryRunResult {
  affected_users: number;
  affected_marketplaces: number;
}

export interface BlockedCountryUpdatePayload {
  reason?: BlockedReason;
  basis?: string;
  note?: string | null;
  review_due_at?: string;
}

export interface BlockedCountriesReviewResult {
  last_reviewed_at: string;
  next_review_due_at: string;
}

export type BlockedCountryAuditAction = "add" | "remove" | "edit" | "review";

export interface BlockedCountryAudit {
  id: string;
  country_code: string;
  action: BlockedCountryAuditAction;
  actor: BlockedCountryActor | null;
  at: string;
  before: unknown;
  after: unknown;
  note: string | null;
}

export interface BlockedCountriesAuditPage {
  items: BlockedCountryAudit[];
  next_cursor: string | null;
}

export interface IpCountryCheck {
  ip: string;
  country: string | null;
  blocked: boolean;
  provider: string;
}

const BLOCKED_COUNTRIES_PATH = "/admin/blocked-countries";

export const getBlockedCountries = () =>
  apiClient.get<BlockedCountriesResponse>(`${BLOCKED_COUNTRIES_PATH}/`);

export const getAvailableCountries = () =>
  apiClient.get<AvailableCountry[]>(`${BLOCKED_COUNTRIES_PATH}/available`);

export const addBlockedCountry = (payload: BlockedCountryCreatePayload) =>
  apiClient.post<BlockedCountry>(`${BLOCKED_COUNTRIES_PATH}/`, payload);

export const dryRunBlockedCountry = (
  payload: Omit<BlockedCountryCreatePayload, "dry_run">,
) =>
  apiClient.post<BlockedCountryDryRunResult>(`${BLOCKED_COUNTRIES_PATH}/`, {
    ...payload,
    dry_run: true,
  });

export const updateBlockedCountry = (
  code: string,
  payload: BlockedCountryUpdatePayload,
) => apiClient.patch<BlockedCountry>(`${BLOCKED_COUNTRIES_PATH}/${code}`, payload);

export const removeBlockedCountry = (code: string) =>
  apiClient.delete<void>(`${BLOCKED_COUNTRIES_PATH}/${code}`);

export const completeBlockedCountriesReview = (note?: string) =>
  apiClient.post<BlockedCountriesReviewResult>(
    `${BLOCKED_COUNTRIES_PATH}/review-complete`,
    { note: note ?? null },
  );

export const getBlockedCountriesAudit = (params?: { limit?: number; cursor?: string | null }) =>
  apiClient.get<BlockedCountriesAuditPage>(`${BLOCKED_COUNTRIES_PATH}/audit`, {
    params: {
      limit: params?.limit ?? 50,
      ...(params?.cursor ? { cursor: params.cursor } : {}),
    },
  });

export const checkIpCountry = (ip: string) =>
  apiClient.get<IpCountryCheck>(`${BLOCKED_COUNTRIES_PATH}/check`, { params: { ip } });
