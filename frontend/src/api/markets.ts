/**
 * Markets API. Typed contracts for new Markets page.
 */

import type { DisplayCurrency } from "@/lib/displayCurrency";
import { apiClient } from "./client";

// --- Preferences ---

export interface MarketsPreferences {
  dashboard_widgets?: string[];
  favorite_instrument_ids: string[];
  forex_favorites?: string[];
  crypto_favorites?: string[];
  commodity_favorites?: string[];
}

export interface MarketsPreferencesUpdate {
  dashboard_widgets?: string[];
  favorite_instrument_ids?: string[];
  forex_favorites?: string[];
  crypto_favorites?: string[];
  commodity_favorites?: string[];
}

export interface MarketsInstrumentOption {
  symbol: string;
  name: string | null;
  rank?: number | null;
  category?: string | null;
  market_cap_usd?: number | null;
}

export interface MarketsInstrumentsResponse {
  forex: MarketsInstrumentOption[];
  crypto: MarketsInstrumentOption[];
  commodities: MarketsInstrumentOption[];
}

// --- Ticker ---

export interface MarketsTickerItem {
  symbol: string;
  name: string | null;
  price: number;
  change_24h: number | null;
  currency: string | null;
  refreshed_at: string;
}

export interface MarketsTickerResponse {
  items: MarketsTickerItem[];
  last_refreshed_at: string | null;
}

// --- Market Overview ---

export interface LocalCurrencyResolution {
  /** ISO 4217 currency code resolved for the marketplace, or null when undeterminable. */
  currency: string | null;
  /** How the currency was resolved: tld | country_code | parse_currency | unknown. */
  source: string;
}

/**
 * Pool item canonical shape from /markets/overview and /pool/products.
 * PP1 dropped the legacy duplicate names (current_price, last_scraped_at,
 * price_change_pct_24h) and the always-None placeholders (original_price,
 * price_change_pct_7d/30d, volatility_30d). Read `price`,
 * `last_checked_at`, and `price_change_pct` instead.
 */
export interface MarketsOverviewItem {
  id: string;
  marketplace_id: string;
  product_id?: string | null;
  marketplace_name?: string | null;
  marketplace_domain?: string | null;
  marketplace_code?: string | null;
  country_code?: string | null;
  url: string;
  title?: string | null;
  image_url?: string | null;
  description?: string | null;
  price?: number | null;
  price_eur?: number | null;
  currency: string;
  display_price?: number | null;
  display_currency?: string | null;
  conversion_available?: boolean;
  local_currency_resolution?: LocalCurrencyResolution | null;
  local_currency_unavailable?: boolean;
  price_change_pct?: number | null;
  in_stock?: boolean | null;
  status: string;
  is_active?: boolean | null;
  last_checked_at?: string | null;
  recent_prices?: Array<{
    date: string;
    price: number;
    currency: string;
    display_price?: number | null;
    display_currency?: string | null;
    conversion_available?: boolean;
  }>;
}

export interface MarketsOverviewResponse {
  items: MarketsOverviewItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface PoolMarketplaceStatsItem {
  marketplace_domain: string;
  marketplace_name?: string | null;
  country_code?: string | null;
  product_count: number;
  avg_price?: number | null;
}

/**
 * /pool/stats shape after PP1 canonical-only cleanup.
 * Legacy duplicates (total_marketplaces, products_with_price,
 * last_discovery_at, message) were removed.
 */
export interface PoolStatsResponse {
  total_products: number;
  total_listings: number;
  marketplaces_count: number;
  listings_with_price: number;
  last_updated?: string | null;
}

// --- Movements (server-side price_change_pct aggregates) ---

export interface MovementsQueryParams {
  country_code?: string;
  period?: "24h" | "7d" | "30d";
  marketplace_id?: string;
  category_id?: string;
  direction?: "up" | "down" | "all";
  threshold?: number;
  limit?: number;
  offset?: number;
  sort_by?: "abs_change" | "changed_at";
}

export interface MoversKpi {
  count: number;
}

export interface MoversSummaryBucket {
  label: string;
  min_pct: number | string;
  max_pct: number | string | null;
  count: number;
}

export interface MoversSummary {
  up_count: number;
  down_count: number;
  unchanged_count: number;
  biggest_gainer: unknown | null;
  biggest_loser: unknown | null;
  avg_abs_change: number | string | null;
  buckets: MoversSummaryBucket[];
}

export interface MoversCoverageMeta {
  listings_with_change: number;
  listings_total: number;
  data_ready: boolean;
}

export interface MoversPage {
  items: unknown[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

// --- API ---

export const marketsApi = {
  getPreferences: () =>
    apiClient.get<MarketsPreferences>("/markets/preferences"),

  getInstruments: () =>
    apiClient.get<MarketsInstrumentsResponse>("/markets/instruments"),

  updatePreferences: (body: MarketsPreferencesUpdate) =>
    apiClient.put<MarketsPreferences>("/markets/preferences", body),

  getTicker: () =>
    apiClient.get<MarketsTickerResponse>("/markets/ticker"),

  getOverview: (params?: {
    sort?: string;
    search?: string;
    marketplace_id?: number;
    limit?: number;
    offset?: number;
    display_currency?: DisplayCurrency;
  }) =>
    apiClient.get<MarketsOverviewResponse>("/markets/overview", {
      params: {
        sort: params?.sort ?? "volatile",
        search: params?.search,
        marketplace_id: params?.marketplace_id,
        limit: params?.limit ?? 50,
        offset: params?.offset ?? 0,
        display_currency: params?.display_currency ?? "local",
      },
    }),

  getPoolMarketplaceStats: () =>
    apiClient.get<PoolMarketplaceStatsItem[]>("/pool/marketplace-stats"),

  getPoolStats: () =>
    apiClient.get<PoolStatsResponse>("/pool/stats"),

  getMovers: (params?: MovementsQueryParams) =>
    apiClient.get<MoversPage>("/markets/movements", { params }),

  getMoversKpi: (params?: MovementsQueryParams) =>
    apiClient.get<MoversKpi>("/markets/movements/kpi", { params }),

  getMoversSummary: (params?: MovementsQueryParams) =>
    apiClient.get<MoversSummary>("/markets/movements/summary", { params }),

  getMoversCoverage: (params?: MovementsQueryParams) =>
    apiClient.get<MoversCoverageMeta>("/markets/movements/coverage", { params }),

  /** Trigger market data ingestion. Superuser only. Enqueues Celery task. */
  triggerIngest: () =>
    apiClient.post<{ status: string; task_id: string }>("/markets/ingest"),
};

// --- Query key helpers ---

export const marketsQueryKeys = {
  all: ["markets"] as const,
  preferences: () => [...marketsQueryKeys.all, "preferences"] as const,
  instruments: () => [...marketsQueryKeys.all, "instruments"] as const,
  ticker: () => [...marketsQueryKeys.all, "ticker"] as const,
  overview: (params?: {
    sort?: string;
    search?: string;
    marketplace_id?: number;
    limit?: number;
    offset?: number;
    display_currency?: DisplayCurrency;
  }) =>
    [
      ...marketsQueryKeys.all,
      "overview",
      params?.sort ?? "volatile",
      params?.search ?? "",
      params?.marketplace_id ?? null,
      params?.limit ?? 50,
      params?.offset ?? 0,
      params?.display_currency ?? "local",
    ] as const,
  poolMarketplaceStats: () => [...marketsQueryKeys.all, "pool-marketplace-stats"] as const,
  poolStats: () => [...marketsQueryKeys.all, "pool-stats"] as const,
  movements: (params?: MovementsQueryParams) =>
    [
      ...marketsQueryKeys.all,
      "movements",
      params?.country_code ?? null,
      params?.period ?? "24h",
      params?.marketplace_id ?? null,
      params?.category_id ?? null,
      params?.direction ?? "all",
      params?.threshold ?? 5,
      params?.limit ?? 20,
      params?.offset ?? 0,
      params?.sort_by ?? "abs_change",
    ] as const,
  movementsKpi: (params?: MovementsQueryParams) =>
    [...marketsQueryKeys.movements(params), "kpi"] as const,
  movementsSummary: (params?: MovementsQueryParams) =>
    [...marketsQueryKeys.movements(params), "summary"] as const,
  movementsCoverage: (params?: MovementsQueryParams) =>
    [...marketsQueryKeys.movements(params), "coverage"] as const,
};
