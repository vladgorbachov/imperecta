import { apiClient } from "./client";

export interface DashboardSummary {
  total_products: number;
  total_competitors: number;
  total_tracked_items: number;
  last_scrape_at: string | null;
  alerts_triggered_today: number;
  price_changes_today: { drops: number; increases: number };
  top_changes: TopChange[];
  active_promos: ActivePromo[];
}

export interface TopChange {
  product_name: string;
  competitor_name: string;
  old_price: number;
  new_price: number;
  change_percent: number;
}

export interface ActivePromo {
  competitor_name: string;
  product_name: string;
  promo_label: string;
}

export interface PriceHistoryDataPoint {
  date: string;
  price: number;
  promo_label: string | null;
  in_stock: boolean;
}

export interface PriceHistoryCompetitor {
  competitor_name: string;
  competitor_product_id: string;
  data_points: PriceHistoryDataPoint[];
}

export interface PriceHistoryResponse {
  product_name: string;
  my_price: number;
  competitors: PriceHistoryCompetitor[];
}

export interface ComparisonCompetitor {
  name: string;
  price: number | null;
  diff_amount: number | null;
  diff_percent: number | null;
  promo_label: string | null;
  in_stock: boolean | null;
  trend: "up" | "down" | "stable";
}

export interface ComparisonResponse {
  my_price: number;
  competitors: ComparisonCompetitor[];
}

export const analyticsApi = {
  getDashboardSummary: () =>
    apiClient.get<DashboardSummary>("/analytics/dashboard/summary"),
  getCompetitorBenchmark: () =>
    apiClient.get<
      Array<{
        id: string;
        name: string;
        marketplace: string;
        priceIndex: number;
        lastChange: number;
        aggressiveness: string;
      }>
    >("/analytics/competitor-benchmark"),
  getAggregateTrend: (period?: number, forecast?: number) =>
    apiClient.get<{
      labels: string[];
      my_products_avg: number[];
      competitors_avg: number[];
      forecast: number[];
      forecast_labels: string[];
    }>("/dashboard/aggregate-trend", {
      params: { period: period ?? 30, forecast: forecast ?? 7 },
    }),
  getPriceHistory: (productId: string, period: "7d" | "30d" | "90d") =>
    apiClient.get<PriceHistoryResponse>(
      `/analytics/products/${productId}/price-history`,
      { params: { period } }
    ),
  getComparison: (productId: string) =>
    apiClient.get<ComparisonResponse>(
      `/analytics/products/${productId}/comparison`
    ),
  getComparisonMatrix: () =>
    apiClient.get<{
      products: { id: string; name: string }[];
      competitors: { id: string; name: string; marketplace: string }[];
      matrix: (number | null)[][];
    }>("/analytics/comparison-matrix"),
  getMarketForecast: (days?: number) =>
    apiClient.get<{ text?: string; confidence?: number; forecast?: unknown }>(
      "/analytics/market-forecast",
      { params: { days: days ?? 7 } }
    ),
};
