import axios from "axios";
import { clearStoredTokens } from "@/lib/authStorage";

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

// --- HTTP 451: service unavailable in the caller's country (compliance) ---

export const BLOCKED_COUNTRY_DETAIL = "service_unavailable_in_your_country";
export const BLOCKED_ROUTE = "/blocked";

/** Matches the fixed backend body `{"detail": "service_unavailable_in_your_country", "country": "XX"}`. */
export function isBlockedCountryResponse(error: unknown): boolean {
  if (!axios.isAxiosError(error) || error.response?.status !== 451) {
    return false;
  }
  const detail = (error.response.data as { detail?: unknown } | undefined)?.detail;
  return detail === BLOCKED_COUNTRY_DETAIL;
}

/**
 * Clears the stored session and sends the browser to the 451 page. A full
 * navigation (not router push) drops in-memory auth state as well; the auth
 * store is not imported here to keep the client free of store cycles.
 */
export function handleBlockedCountryError(
  error: unknown,
  navigate: (path: string) => void = (path) => window.location.assign(path),
): Promise<never> {
  if (isBlockedCountryResponse(error)) {
    clearStoredTokens();
    if (typeof window === "undefined" || window.location.pathname !== BLOCKED_ROUTE) {
      navigate(BLOCKED_ROUTE);
    }
  }
  return Promise.reject(error);
}

apiClient.interceptors.response.use((response) => response, (error) => handleBlockedCountryError(error));
publicClient.interceptors.response.use((response) => response, (error) => handleBlockedCountryError(error));
