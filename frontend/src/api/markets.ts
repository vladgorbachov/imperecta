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
  bid: number;
  ask: number;
  spread: number;
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
  id: string;
  marketplace: string;
  marketplace_domain: string;
  product_name: string;
  price: number;
  currency: string;
  change_24h: number | null;
  change_3d: number | null;
  change_1w: number | null;
  change_1m: number | null;
  sparkline_data: number[];
  last_updated: string;
  /** Optional product thumbnail. When absent, show placeholder. */
  thumbnail_url?: string | null;
}

export interface MarketsOverviewResponse {
  items: MarketsOverviewItem[];
  total: number;
  sort: string;
  last_refreshed_at: string | null;
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

  getOverview: (sort?: string, limit?: number) =>
    apiClient.get<MarketsOverviewResponse>("/markets/overview", {
      params: { sort: sort ?? "volatile", limit: limit ?? 50 },
    }),

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
  overview: (sort?: string, limit?: number) =>
    [...marketsQueryKeys.all, "overview", sort ?? "volatile", limit ?? 50] as const,
  categoryAnalytics: () => [...marketsQueryKeys.all, "category-analytics"] as const,
  marketplaceAnalytics: () => [...marketsQueryKeys.all, "marketplace-analytics"] as const,
  opportunities: () => [...marketsQueryKeys.all, "opportunities"] as const,
};
