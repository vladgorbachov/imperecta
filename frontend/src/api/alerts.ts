import { apiClient } from "./client";

export const alertsApi = {
  list: () => apiClient.get("/alerts"),
  create: (data: { product_id?: number; threshold_percent?: number; channel: string }) =>
    apiClient.post("/alerts", data),
  update: (id: number, data: Partial<{ is_active: boolean }>) =>
    apiClient.patch(`/alerts/${id}`, data),
  delete: (id: number) => apiClient.delete(`/alerts/${id}`),
};
