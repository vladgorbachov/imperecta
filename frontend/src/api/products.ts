import { apiClient } from "./client";

export const productsApi = {
  list: () => apiClient.get("/products"),
  create: (data: { name: string; sku?: string; base_price?: number }) =>
    apiClient.post("/products", data),
  get: (id: number) => apiClient.get(`/products/${id}`),
  update: (id: number, data: Partial<{ name: string; sku: string; base_price: number }>) =>
    apiClient.patch(`/products/${id}`, data),
  delete: (id: number) => apiClient.delete(`/products/${id}`),
};
