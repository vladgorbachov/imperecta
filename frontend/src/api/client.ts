import axios from "axios";

// VITE_API_URL: absolute URL for production (Cloudflare Pages); empty = Vite proxy in dev
let API_URL = import.meta.env.VITE_API_URL || "";
// Force HTTPS when page is served over HTTPS to avoid Mixed Content blocking
if (typeof window !== "undefined" && window.location?.protocol === "https:" && API_URL.startsWith("http://")) {
  API_URL = API_URL.replace("http://", "https://");
}
export const apiBaseUrl = API_URL ? `${API_URL}/api` : "/api";

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

// Interceptors are configured in setupAuth.ts (after authStore is available)
