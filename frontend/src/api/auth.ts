import { apiClient } from "./client";

export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post<{ access_token: string; refresh_token: string }>(
      "/auth/login",
      { email, password }
    ),
  register: (
    email: string,
    password: string,
    name: string,
    companyName?: string,
    language?: string
  ) =>
    apiClient.post<{ access_token: string; refresh_token: string }>(
      "/auth/register",
      { email, password, name, company_name: companyName ?? null, language: language ?? "en" }
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
      created_at: string;
      telegram_chat_id: number | null;
    }>("/auth/me"),
  updateMe: (data: {
    name?: string;
    company_name?: string;
    language?: string;
  }) => apiClient.put("/auth/me", data),
  getTelegramLink: () =>
    apiClient.post<{ code: string; bot_url: string }>("/auth/telegram-link"),
  disconnectTelegram: () =>
    apiClient.post<{ ok: boolean }>("/auth/telegram-disconnect"),
};
