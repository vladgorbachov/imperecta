/**
 * Configures axios interceptors for auth: token injection and 401 refresh.
 * Must be imported after apiClient and authStore are available.
 */

import { apiClient } from "./client";
import { useAuthStore } from "@/stores/authStore";
import { getStoredToken } from "@/lib/authStorage";

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

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const success = await useAuthStore.getState().refreshAccessToken();

      if (success) {
        const token = useAuthStore.getState().accessToken;
        if (token) {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        }
      }

      useAuthStore.getState().logout();
    }

    return Promise.reject(error);
  }
);
