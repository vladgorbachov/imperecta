import { apiClient } from "./client";

export const authApi = {
  login: (email: string, password: string, remember_me?: boolean) =>
    apiClient.post<{
      access_token: string;
      refresh_token: string;
      persistent?: boolean;
      expires_at?: string;
      force_password_change?: boolean;
    }>("/auth/login", { email, password, remember_me: remember_me ?? false }),
  refresh: (refresh_token: string) =>
    apiClient.post<{
      access_token: string;
      refresh_token: string;
      persistent?: boolean;
      expires_at?: string;
    }>("/auth/refresh", { refresh_token }),
  register: (
    email: string,
    password: string,
    name: string,
    companyName?: string,
    language?: string
  ) =>
    apiClient.post<{
      access_token: string;
      refresh_token: string;
      persistent?: boolean;
      expires_at?: string;
    }>(
      "/auth/register",
      { email, password, name, company_name: companyName ?? null, language }
    ),
  getMe: () =>
    apiClient.get<{
      id: string;
      email: string;
      name: string;
      company_name: string | null;
      plan: string;
      trial_ends_at: string | null;
      language: string;
      timezone?: string | null;
      ai_tone?: string;
      default_currency?: string | null;
      created_at: string;
      telegram_chat_id: number | null;
      avatar_url: string | null;
      is_superuser?: boolean;
      is_active?: boolean;
      force_password_change?: boolean;
      preferences?: Record<string, unknown> | null;
      entitlements?: {
        service_tier: string;
        features: Record<string, boolean>;
        limits: Record<string, number>;
        trial_duration_days?: number;
        is_trial_expired?: boolean;
      };
    }>("/users/me"),
  updateMe: (data: {
    name?: string;
    company_name?: string;
    language?: string;
    timezone?: string;
    avatar_url?: string | null;
    ai_tone?: string;
    preferences?: Record<string, unknown>;
  }) => apiClient.put("/users/me", data),
  deleteAvatar: () => apiClient.delete<{ message: string }>("/auth/avatar"),
  getTelegramLink: () =>
    apiClient.post<{ code: string; bot_url: string }>("/auth/telegram-link"),
  disconnectTelegram: () =>
    apiClient.post<{ ok: boolean }>("/auth/telegram-disconnect"),
};
