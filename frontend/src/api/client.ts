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

/**
 * Anonymous client for the public storefront reads (pool, market KPIs,
 * news). It deliberately sends NO Authorization header: the backend stamps
 * anonymous responses `Cache-Control: public, s-maxage=300,
 * stale-while-revalidate=600`, so the CDN in front of the API serves them
 * from the edge for every viewer. A token would make the response
 * `private` and drop it out of the shared cache (see
 * backend/app/common/public_cache.py). Never use it for user-scoped or
 * write endpoints.
 */
export const publicClient = axios.create({
  baseURL: apiBaseUrl,
  headers: { Accept: "application/json" },
});
