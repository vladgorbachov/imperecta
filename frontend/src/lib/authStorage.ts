/**
 * Auth token storage: localStorage (persistent) or sessionStorage (session-only).
 * Used by authStore and api client.
 */

import { clearAuthCookie } from "./authCookie";

export const STORAGE_KEY = "imperecta_auth";
export const SESSION_STORAGE_KEY = "imperecta_auth_session";

export interface SavedAuth {
  accessToken: string;
  refreshToken: string;
  persistent: boolean;
  expiresAt: string;
  user: unknown;
  savedAt: string;
}

export function loadTokens(): SavedAuth | null {
  const persistent = localStorage.getItem(STORAGE_KEY);
  if (persistent) {
    try {
      return JSON.parse(persistent) as SavedAuth;
    } catch {
      return null;
    }
  }
  const session = sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (session) {
    try {
      return JSON.parse(session) as SavedAuth;
    } catch {
      return null;
    }
  }
  return null;
}

export function clearStoredTokens(): void {
  localStorage.removeItem(STORAGE_KEY);
  sessionStorage.removeItem(SESSION_STORAGE_KEY);
  clearAuthCookie();
}

export function getStoredToken(): string | null {
  const saved = loadTokens();
  return saved?.accessToken ?? null;
}

export function saveTokens(data: {
  accessToken: string;
  refreshToken: string;
  persistent: boolean;
  expiresAt: string | null;
  user: unknown;
}): void {
  const payload: SavedAuth = {
    ...data,
    expiresAt: data.expiresAt ?? "",
    savedAt: new Date().toISOString(),
  };
  const json = JSON.stringify(payload);
  if (data.persistent) {
    localStorage.setItem(STORAGE_KEY, json);
    sessionStorage.removeItem(SESSION_STORAGE_KEY);
  } else {
    sessionStorage.setItem(SESSION_STORAGE_KEY, json);
    localStorage.removeItem(STORAGE_KEY);
  }
}
