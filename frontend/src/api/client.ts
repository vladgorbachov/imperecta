import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL;
if (!API_URL) {
  throw new Error("VITE_API_URL is required");
}

// Force HTTPS when page is served over HTTPS to avoid Mixed Content blocking
const normalizedApiUrl =
  typeof window !== "undefined" &&
  window.location?.protocol === "https:" &&
  API_URL.startsWith("http://")
    ? API_URL.replace("http://", "https://")
    : API_URL;

export const apiBaseUrl = `${normalizedApiUrl}/api`;

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

// Interceptors are configured in setupAuth.ts (after authStore is available)
