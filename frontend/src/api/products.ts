import { apiClient } from "./client";

export interface Product {
  id: string;
  user_id: string;
  name: string;
  sku: string | null;
  current_price: number;
  currency: string;
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
  last_checked_at: string | null;
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
    page?: number;
    limit?: number;
  }) => apiClient.get<ProductListResponse>("/products", { params }),
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
};
