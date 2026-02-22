import { apiClient } from "./client";

export interface Alert {
  id: string;
  product_id: string | null;
  product_name: string | null;
  type: string;
  threshold_percent: number | null;
  channel: string;
  is_active: boolean;
  created_at: string;
}

export interface AlertEvent {
  id: number;
  alert_id: string;
  product_name: string | null;
  competitor_name: string | null;
  old_price: number | null;
  new_price: number | null;
  message: string;
  sent_via: string;
  triggered_at: string;
}

export const alertsApi = {
  list: () => apiClient.get<Alert[]>("/alerts"),
  create: (data: {
    product_id?: string;
    type: string;
    threshold_percent?: number;
    channel: string;
  }) => apiClient.post<Alert>("/alerts", data),
  update: (id: string, data: { is_active?: boolean }) =>
    apiClient.put<Alert>(`/alerts/${id}`, data),
  delete: (id: string) => apiClient.delete(`/alerts/${id}`),
  getEvents: (limit?: number) =>
    apiClient.get<AlertEvent[]>("/alerts/events", {
      params: limit ? { limit } : undefined,
    }),
};
