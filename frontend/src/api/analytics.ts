import { apiClient } from "./client";

export const analyticsApi = {
  priceHistory: (productId: number, period?: string) =>
    apiClient.get(`/analytics/price-history/${productId}`, { params: { period } }),
  trends: (productId: number) => apiClient.get(`/analytics/trends/${productId}`),
};
