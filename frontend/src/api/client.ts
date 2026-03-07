import axios from "axios";

// VITE_API_URL: absolute URL for production (Cloudflare Pages); empty = Vite proxy in dev
const API_URL = import.meta.env.VITE_API_URL || "";
export const apiBaseUrl = API_URL ? `${API_URL}/api` : "/api";

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

// Interceptors are configured in setupAuth.ts (after authStore is available)
