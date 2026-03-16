/**
 * Markets API. Typed contracts for new Markets page.
 */

import { apiClient } from "./client";

// --- Preferences ---

export interface MarketsPreferences {
  preferred_country_code: string | null;
  favorite_instrument_ids: string[];
  favorite_forex?: string[];
  favorite_crypto?: string[];
  favorite_commodities?: string[];
}

export interface MarketsPreferencesUpdate {
  preferred_country_code?: string | null;
  favorite_instrument_ids?: string[];
  favorite_forex?: string[];
  favorite_crypto?: string[];
  favorite_commodities?: string[];
}

// --- Refresh metadata ---

export interface MarketsRefreshStatusItem {
  refresh_type: string;
  last_successful_refresh: string | null;
  last_failed_refresh: string | null;
  provider_source: string | null;
  country_scope: string | null;
  error_message: string | null;
}

export interface MarketsRefreshMetadata {
  items: MarketsRefreshStatusItem[];
}

// --- Forex ---

export interface MarketsForexItem {
  symbol: string;
  /** Backend may return "rate" or "bid". Use rate ?? bid for compatibility. */
  rate?: number;
  bid?: number;
  ask?: number;
  spread?: number;
  change_24h: number | null;
  refreshed_at: string;
}

export interface MarketsForexResponse {
  items: MarketsForexItem[];
  last_refreshed_at: string | null;
}

// --- Crypto ---

export interface MarketsCryptoItem {
  symbol: string;
  price: number;
  change_24h: number | null;
  market_cap: number | null;
  refreshed_at: string;
}

export interface MarketsCryptoResponse {
  items: MarketsCryptoItem[];
  error: string | null;
  cached: boolean;
  last_refreshed_at: string | null;
}

// --- Commodities ---

export interface MarketsCommodityItem {
  symbol: string;
  name: string | null;
  price: number;
  change_24h: number | null;
  unit: string | null;
  refreshed_at: string;
}

export interface MarketsCommoditiesResponse {
  items: MarketsCommodityItem[];
  error: string | null;
  cached: boolean;
  last_refreshed_at: string | null;
}

// --- Fuel ---

export interface FuelResponse {
  country?: string;
  gasoline_95: number;
  diesel: number;
  lpg: number;
  currency: string;
  unit: string;
  updated?: string;
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

export interface MarketsOverviewItem {
  id: number;
  marketplace_id: number;
  marketplace_name?: string | null;
  marketplace_domain?: string | null;
  url: string;
  title?: string | null;
  image_url?: string | null;
  description?: string | null;
  current_price?: number | null;
  original_price?: number | null;
  currency: string;
  price_change_pct_24h?: number | null;
  price_change_pct_7d?: number | null;
  price_change_pct_30d?: number | null;
  volatility_30d?: number | null;
  status: string;
  last_scraped_at?: string | null;
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
  product_count: number;
  avg_price?: number | null;
}

export interface PoolStatsResponse {
  total_products: number;
  total_marketplaces: number;
  products_with_price: number;
  last_discovery_at?: string | null;
}

// --- Category analytics ---

export interface MarketsCategoryAnalyticsItem {
  id: string;
  category_id: string;
  segment: string | null;
  metrics: Record<string, unknown>;
  refreshed_at: string;
}

export interface MarketsCategoryAnalyticsResponse {
  items: MarketsCategoryAnalyticsItem[];
  last_refreshed_at: string | null;
}

// --- Marketplace analytics ---

export interface MarketsMarketplaceAnalyticsItem {
  id: string;
  marketplace_id: string;
  marketplace_name: string | null;
  metrics: Record<string, unknown>;
  refreshed_at: string;
}

export interface MarketsMarketplaceAnalyticsResponse {
  items: MarketsMarketplaceAnalyticsItem[];
  last_refreshed_at: string | null;
}

// --- Opportunity blocks ---

export interface MarketsOpportunityBlockItem {
  id: string;
  block_type: string;
  title: string;
  metrics: Record<string, unknown>;
  refreshed_at: string;
}

export interface MarketsOpportunitiesResponse {
  items: MarketsOpportunityBlockItem[];
  last_refreshed_at: string | null;
}

// --- API ---

export interface CountryItem {
  code: string;
  name: string;
  name_local?: string;
  flag?: string;
  region?: string;
  is_region?: boolean;
  separator?: boolean;
}

export const marketsApi = {
  getCountries: () =>
    apiClient.get<CountryItem[]>("/markets/countries"),

  getPreferences: () =>
    apiClient.get<MarketsPreferences>("/markets/preferences"),

  updatePreferences: (body: MarketsPreferencesUpdate) =>
    apiClient.put<MarketsPreferences>("/markets/preferences", body),

  getRefreshMetadata: () =>
    apiClient.get<MarketsRefreshMetadata>("/markets/refresh-metadata"),

  getForex: () =>
    apiClient.get<MarketsForexResponse>("/markets/forex"),

  getCrypto: () =>
    apiClient.get<MarketsCryptoResponse>("/markets/crypto"),

  getCommodities: () =>
    apiClient.get<MarketsCommoditiesResponse>("/markets/commodities"),

  getTicker: (country?: string) =>
    apiClient.get<MarketsTickerResponse>("/markets/ticker", {
      params: country ? { country } : undefined,
    }),

  getFuel: (country: string) =>
    apiClient.get<FuelResponse>(`/markets/fuel?country=${encodeURIComponent(country)}`),

  getOverview: (params?: {
    sort?: string;
    search?: string;
    marketplace_id?: number;
    limit?: number;
    offset?: number;
  }) =>
    apiClient.get<MarketsOverviewResponse>("/markets/overview", {
      params: {
        sort: params?.sort ?? "volatile",
        search: params?.search,
        marketplace_id: params?.marketplace_id,
        limit: params?.limit ?? 50,
        offset: params?.offset ?? 0,
      },
    }),

  getPoolMarketplaceStats: () =>
    apiClient.get<PoolMarketplaceStatsItem[]>("/pool/marketplace-stats"),

  getPoolStats: () =>
    apiClient.get<PoolStatsResponse>("/pool/stats"),

  getCategoryAnalytics: () =>
    apiClient.get<MarketsCategoryAnalyticsResponse>("/markets/category-analytics"),

  getMarketplaceAnalytics: () =>
    apiClient.get<MarketsMarketplaceAnalyticsResponse>("/markets/marketplace-analytics"),

  getOpportunities: () =>
    apiClient.get<MarketsOpportunitiesResponse>("/markets/opportunities"),

  /** Trigger market data ingestion. Superuser only. Enqueues Celery task. */
  triggerIngest: () =>
    apiClient.post<{ status: string; task_id: string }>("/markets/ingest"),
};

// --- Query key helpers ---

export const marketsQueryKeys = {
  all: ["markets"] as const,
  countries: () => [...marketsQueryKeys.all, "countries"] as const,
  preferences: () => [...marketsQueryKeys.all, "preferences"] as const,
  refreshMetadata: () => [...marketsQueryKeys.all, "refresh-metadata"] as const,
  forex: () => [...marketsQueryKeys.all, "forex"] as const,
  crypto: () => [...marketsQueryKeys.all, "crypto"] as const,
  commodities: () => [...marketsQueryKeys.all, "commodities"] as const,
  ticker: (country?: string) =>
    [...marketsQueryKeys.all, "ticker", country ?? ""] as const,
  fuel: (country: string) =>
    [...marketsQueryKeys.all, "fuel", country] as const,
  overview: (params?: {
    sort?: string;
    search?: string;
    marketplace_id?: number;
    limit?: number;
    offset?: number;
  }) =>
    [
      ...marketsQueryKeys.all,
      "overview",
      params?.sort ?? "volatile",
      params?.search ?? "",
      params?.marketplace_id ?? null,
      params?.limit ?? 50,
      params?.offset ?? 0,
    ] as const,
  poolMarketplaceStats: () => [...marketsQueryKeys.all, "pool-marketplace-stats"] as const,
  poolStats: () => [...marketsQueryKeys.all, "pool-stats"] as const,
  categoryAnalytics: () => [...marketsQueryKeys.all, "category-analytics"] as const,
  marketplaceAnalytics: () => [...marketsQueryKeys.all, "marketplace-analytics"] as const,
  opportunities: () => [...marketsQueryKeys.all, "opportunities"] as const,
};
