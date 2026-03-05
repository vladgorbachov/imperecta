import axios from "axios";

const TOKEN_KEY = "access_token";

// VITE_API_URL: absolute URL for production (Cloudflare Pages); empty = Vite proxy in dev
const API_URL = import.meta.env.VITE_API_URL || "";
export const apiBaseUrl = API_URL ? `${API_URL}/api` : "/api";

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearStoredTokens();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

const AUTH_TOKEN_KEY = "auth_token";

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearStoredTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem("refresh_token");
}

export function getAuthToken(): string | null {
  const auth = localStorage.getItem(AUTH_TOKEN_KEY);
  const access = localStorage.getItem(TOKEN_KEY);
  if (auth) return auth;
  if (access) {
    localStorage.setItem(AUTH_TOKEN_KEY, access);
    return access;
  }
  return null;
}
