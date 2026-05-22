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
  name: string;
  url: string;
  products_in_pool: number;
  last_successful_scrape: string | null;
  success_rate: number;
  last_run: string | null;
  status: "running" | "completed" | "failed";
}

export interface ParsingRunCreateResponse {
  job_id: string;
  started_at: string;
}

export interface ParsingTestRun {
  job_id: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  listings_created: number;
  prices_saved: number;
  errors_count: number;
  status: "running" | "completed" | "failed";
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
  error?: string;
}

export interface ParsingJobStatus {
  job_id: string;
  status: "running" | "completed" | "failed";
  current_stage: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  metadata: ParsingJobMetadata | null;
}

export const getParsingTestMarketplaces = () =>
  apiClient.get<ParsingTestMarketplace[]>("/admin/parsing/test-marketplaces");

export const runParsingFullTest = () =>
  apiClient.post<ParsingRunCreateResponse>("/admin/parsing/run-full-test");

export const getParsingTestRuns = (limit = 50) =>
  apiClient.get<ParsingTestRun[]>("/admin/parsing/test-runs", { params: { limit } });

export const getParsingJobStatus = (jobId: string) =>
  apiClient.get<ParsingJobStatus>(`/admin/parsing/job-status/${jobId}`);
