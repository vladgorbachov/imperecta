/**
 * Configures axios interceptors for auth: token injection and 401 refresh.
 * Must be imported after apiClient and authStore are available.
 *
 * Refresh coordination: only one refresh runs at a time; concurrent 401s
 * wait for the same refresh promise instead of each triggering their own.
 */

import { apiClient } from "./client";
import { useAuthStore } from "@/stores/authStore";
import { getStoredToken } from "@/lib/authStorage";

/** In-flight refresh promise. All concurrent 401s await this instead of starting new refreshes. */
let refreshPromise: Promise<boolean> | null = null;

function isRefreshRequest(config: { url?: string; baseURL?: string }): boolean {
  const url = config.url ?? "";
  const base = config.baseURL ?? "";
  const full = url.startsWith("http") ? url : `${base}${url}`;
  return full.includes("/auth/refresh");
}

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken ?? getStoredToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    if (isRefreshRequest(originalRequest)) {
      useAuthStore.getState().logout();
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    if (!refreshPromise) {
      refreshPromise = useAuthStore
        .getState()
        .refreshAccessToken()
        .finally(() => {
          refreshPromise = null;
        });
    }

    const success = await refreshPromise;

    if (success) {
      const token = useAuthStore.getState().accessToken;
      if (token) {
        originalRequest.headers.Authorization = `Bearer ${token}`;
        return apiClient(originalRequest);
      }
    }

    useAuthStore.getState().logout();
    return Promise.reject(error);
  }
);
