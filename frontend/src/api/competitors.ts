import { apiClient } from "./client";

export const competitorsApi = {
  list: (productId?: number) =>
    apiClient.get("/competitors", productId ? { params: { product_id: productId } } : {}),
  create: (data: { product_id: number; url: string; marketplace: string }) =>
    apiClient.post("/competitors", data),
  delete: (id: number) => apiClient.delete(`/competitors/${id}`),
};
