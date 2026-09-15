/**
 * Client price-alerts API (P3): rules CRUD + events feed.
 * Strictly user-scoped on the backend; foreign rule ids return 404.
 */

import { apiClient } from "@/api/client";

export type AlertType = "price_drop" | "price_rise" | "availability";
export type AlertChannel = "email" | "telegram" | "webhook";

export interface AlertRule {
  id: string;
  listing_id: string | null;
  product_id: string | null;
  marketplace_id: string | null;
  alert_type: AlertType;
  threshold_pct: number | null;
  channel: AlertChannel;
  webhook_url: string | null;
  cooldown_minutes: number;
  is_active: boolean;
  last_triggered_at: string | null;
  trigger_count: number;
  created_at: string;
  product_title: string | null;
  marketplace_name: string | null;
}

export interface AlertRuleCreatePayload {
  listing_id?: string | null;
  product_id?: string | null;
  marketplace_id?: string | null;
  alert_type: AlertType;
  threshold_pct?: number | null;
  channel: AlertChannel;
  webhook_url?: string | null;
  cooldown_minutes?: number;
}

export interface AlertEvent {
  id: string;
  rule_id: string;
  alert_type: AlertType;
  product_title: string | null;
  marketplace_name: string | null;
  old_price: number | string | null;
  new_price: number | string | null;
  currency: string | null;
  change_pct: number | string | null;
  triggered_at: string;
}

export interface AlertRulesResponse {
  items: AlertRule[];
  total: number;
}

export interface AlertEventsResponse {
  items: AlertEvent[];
  total: number;
  limit: number;
  offset: number;
}

export const alertsApi = {
  listRules: () => apiClient.get<AlertRulesResponse>("/alerts"),

  createRule: (payload: AlertRuleCreatePayload) =>
    apiClient.post<AlertRule>("/alerts", payload),

  updateRule: (id: string, payload: Partial<AlertRuleCreatePayload> & { is_active?: boolean }) =>
    apiClient.patch<AlertRule>(`/alerts/${id}`, payload),

  deleteRule: (id: string) => apiClient.delete<void>(`/alerts/${id}`),

  listEvents: (params?: { limit?: number; offset?: number }) =>
    apiClient.get<AlertEventsResponse>("/alerts/events", { params }),
};
