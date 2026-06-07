import type { DisplayCurrency } from "@/lib/displayCurrency";
import type { LocalCurrencyResolution } from "./markets";
import { apiClient } from "./client";

export type { LocalCurrencyResolution };

// --- Pool products (global marketplace pool) ---

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

export interface PoolProductItem {
  id: string;
  marketplace_id: string;
  product_id?: string | null;
  marketplace_name?: string | null;
  marketplace_domain?: string | null;
  country_code?: string | null;
  url: string;
  title?: string | null;
  image_url?: string | null;
  description?: string | null;
  current_price?: number | null;
  original_price?: number | null;
  currency: string;
  display_price?: number | null;
  display_currency?: string | null;
  conversion_available?: boolean;
  local_currency_resolution?: LocalCurrencyResolution | null;
  local_currency_unavailable?: boolean;
  price_change_pct_24h?: number | null;
  price_change_pct_7d?: number | null;
  price_change_pct_30d?: number | null;
  volatility_30d?: number | null;
  status: string;
  last_scraped_at?: string | null;
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

export interface Product {
  id: string;
  user_id: string;
  name: string;
  sku: string | null;
  current_price: number;
  currency: string;
  display_price?: number | null;
  display_currency?: string | null;
  conversion_available?: boolean;
  url: string | null;
  category: string | null;
  is_active: boolean;
  competitor_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProductListItem extends Product {
  min_competitor_price: number | null;
  max_competitor_price: number | null;
  min_competitor_display_price?: number | null;
  max_competitor_display_price?: number | null;
  last_checked_at: string | null;
  local_currency_resolution?: LocalCurrencyResolution | null;
  local_currency_unavailable?: boolean;
}

export interface ProductListResponse {
  items: ProductListItem[];
  total: number;
}

export interface ProductDetail {
  id: string;
  name: string;
  sku: string | null;
  current_price: number;
  currency: string;
  competitor_products: CompetitorProductBrief[];
}

export interface CompetitorProductBrief {
  id: string;
  competitor_id: string;
  competitor_name: string;
  url: string;
  name: string | null;
  last_price: number | null;
  last_promo_label: string | null;
  last_in_stock: boolean | null;
  last_checked_at: string | null;
}

export const productsApi = {
  list: (params?: {
    search?: string;
    category?: string;
    sort?: string;
    page?: number;
    limit?: number;
    display_currency?: DisplayCurrency;
  }) => apiClient.get<ProductListResponse>("/products", { params }),

  fetchPoolProducts: (params: PoolProductsParams) =>
    apiClient.get<PoolProductsResponse>("/pool/products", { params }),

  getPoolCategories: () =>
    apiClient.get<PoolCategoryItem[]>("/pool/categories"),
  get: (id: string) => apiClient.get<ProductDetail>(`/products/${id}`),
  getCategories: () =>
    apiClient.get<string[]>("/products/categories"),
  create: (data: {
    name: string;
    sku?: string;
    current_price: number;
    currency?: string;
    url?: string;
    category?: string;
  }) => apiClient.post<Product>("/products", data),
  update: (
    id: string,
    data: Partial<{
      name: string;
      sku: string;
      current_price: number;
      category: string;
    }>
  ) => apiClient.put<Product>(`/products/${id}`, data),
  delete: (id: string) => apiClient.delete(`/products/${id}`),

  /** Bulk delete user products by IDs */
  bulkDelete: (productIds: string[]) =>
    apiClient.delete<{ deleted: number }>("/products/bulk", {
      data: { product_ids: productIds },
    }),

  /** Delete ALL user products */
  deleteAll: () =>
    apiClient.delete<{ deleted: number }>("/products/all"),

  /** Bulk delete pool products (superuser only) */
  bulkDeletePool: (productIds: number[]) =>
    apiClient.delete<{ deleted: number }>("/pool/products/bulk", {
      data: { product_ids: productIds },
    }),
};
