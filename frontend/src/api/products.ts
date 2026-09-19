import type { DisplayCurrency } from "@/lib/displayCurrency";
import type { LocalCurrencyResolution } from "./markets";
import { publicClient } from "./client";
import { dataOpsApi } from "./dataOps";

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
  /** Skip the count(*) entirely (typeahead paths); the response total is null. */
  skip_total?: boolean;
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
  /** Source attribution (WP2): domain of the original listing + link to it. */
  source_domain?: string | null;
  external_url?: string | null;
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
  /** Taxonomy fields — present once the backend adds them to the LIST
      response (P10/P13 in docs/FRONTEND_BACKEND_REQUESTS.md); detail has
      brand/category already. EN variants are the universal-language layer. */
  brand?: string | null;
  category?: string | null;
  category_en?: string | null;
  product_type?: string | null;
  product_type_en?: string | null;
  title_en?: string | null;
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
  /** null when the request passed skip_total=true (no count executed). */
  total: number | null;
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

/** Extended detail returned by GET /pool/products/{id} (P2). */
export interface PoolProductDetail extends PoolProductItem {
  attributes?: Record<string, unknown> | null;
  brand?: string | null;
  category?: string | null;
}

export type PriceHistoryPeriod = "7d" | "30d" | "90d";

/** GET /pool/products/{id}/price-history response (P1). */
export interface PriceHistoryResponse {
  listing_id: string;
  currency: string;
  period: PriceHistoryPeriod;
  points: Array<{ date: string; price: number; price_eur: number | null }>;
  data_ready: boolean;
}

export const productsApi = {
  /**
   * Grid/search read path lives in the Rust data-ops service (in-memory
   * search index, keyset paging); the FastAPI twin is the fallback when
   * data-ops is unreachable or errors. Both require the user's JWT (WP2).
   */
  fetchPoolProducts: async (params: PoolProductsParams) => {
    try {
      return await dataOpsApi.fetchPoolProducts(params);
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status !== undefined && status < 500) throw err;
      return publicClient.get<PoolProductsResponse>("/pool/products", { params });
    }
  },

  getPoolCategories: () =>
    publicClient.get<PoolCategoryItem[]>("/pool/categories"),

  getPoolProduct: (listingId: string, displayCurrency?: DisplayCurrency) =>
    publicClient.get<PoolProductDetail>(`/pool/products/${listingId}`, {
      params: displayCurrency ? { display_currency: displayCurrency } : undefined,
    }),

  getPriceHistory: (listingId: string, period: PriceHistoryPeriod = "30d") =>
    publicClient.get<PriceHistoryResponse>(
      `/pool/products/${listingId}/price-history`,
      { params: { period, bucket: "day" } },
    ),
};
