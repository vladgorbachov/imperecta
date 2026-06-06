import type { DisplayCurrency } from "@/lib/displayCurrency";
import { apiClient } from "./client";

export interface Competitor {
  id: string;
  user_id: string;
  name: string;
  website_url: string | null;
  marketplace: string;
  notes: string | null;
  created_at: string;
  product_count: number;
}

export interface CompetitorProduct {
  id: string;
  product_id: string;
  competitor_id: string;
  competitor_name: string;
  url: string;
  name: string | null;
  last_price: number | null;
  currency?: string | null;
  display_price?: number | null;
  display_currency?: string | null;
  conversion_available?: boolean;
  last_promo_label: string | null;
  last_in_stock: boolean | null;
  last_checked_at: string | null;
  scraper_type: string;
  css_selector_price: string | null;
  is_active: boolean;
  created_at: string;
  price_diff: number | null;
}

export interface MarketplaceOption {
  marketplace_id: string;
  name: string;
}

export interface ScrapeTriggerResponse {
  status: string;
  task_id: string;
  competitor_product_id: string;
}

export const competitorsApi = {
  list: () => apiClient.get<Competitor[]>("/competitors"),
  listMarketplaces: () =>
    apiClient.get<MarketplaceOption[]>("/competitors/marketplaces"),
  create: (data: {
    name: string;
    website_url?: string;
    marketplace: string;
    notes?: string;
  }) => apiClient.post<Competitor>("/competitors", data),
  getProducts: (competitorId: string, displayCurrency?: DisplayCurrency) =>
    apiClient.get<CompetitorProduct[]>(`/competitors/${competitorId}/products`, {
      params: { display_currency: displayCurrency ?? "local" },
    }),
  addProduct: (data: {
    product_id: string;
    competitor_id: string;
    url: string;
    name?: string;
    scraper_type?: string;
  }) => apiClient.post<CompetitorProduct>("/competitors/products", data),
  deleteProduct: (id: string) =>
    apiClient.delete(`/competitors/products/${id}`),
  triggerProductScrape: (id: string) =>
    apiClient.post<ScrapeTriggerResponse>(`/competitors/products/${id}/scrape`),
  delete: (id: string) => apiClient.delete(`/competitors/${id}`),
};
