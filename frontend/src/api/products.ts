import type { DisplayCurrency } from "@/lib/displayCurrency";
import type { LocalCurrencyResolution } from "./markets";
import { apiClient } from "./client";

export type { LocalCurrencyResolution };

// --- Pool products (global marketplace pool) ---
// User-products endpoints were removed in UP1; user_products module is empty
// pending Phase 4 (Ingestion-rail rebuild). Only pool endpoints remain here.

export type PoolProductsSort =
  | "recent"
  | "name_asc"
  | "name_desc"
  | "price_asc"
  | "price_desc"
  | "trending"
  | "gainers"
  | "losers"
  | "volatile";

export interface PoolProductsParams {
  search?: string;
  marketplace_id?: string;
  category?: string;
  sort?: PoolProductsSort;
  limit?: number;
  offset?: number;
  display_currency?: DisplayCurrency;
}

/**
 * Pool item canonical shape from /pool/products. PP1 dropped the legacy
 * duplicate names (current_price, last_scraped_at, price_change_pct_24h)
 * and the always-None placeholders (original_price, price_change_pct_7d/30d,
 * volatility_30d). Read `price`, `last_checked_at`, `price_change_pct`.
 */
export interface PoolProductItem {
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
  }>;
}

export interface PoolProductsResponse {
  items: PoolProductItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface PoolCategoryItem {
  marketplace_id: string;
  marketplace_code?: string;
  name: string;
  domain: string;
  country_code?: string | null;
  listing_count: number;
}

export const productsApi = {
  fetchPoolProducts: (params: PoolProductsParams) =>
    apiClient.get<PoolProductsResponse>("/pool/products", { params }),

  getPoolCategories: () =>
    apiClient.get<PoolCategoryItem[]>("/pool/categories"),
};
