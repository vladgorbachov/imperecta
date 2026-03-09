/**
 * Auth cookie for edge routing (Cloudflare Pages middleware).
 * Lightweight presence indicator — not the source of truth for authorization.
 * Backend/API auth remains token-based.
 */

export const AUTH_COOKIE_NAME = "imperecta_auth";

/**
 * Sets the auth cookie when user logs in or restores session.
 * Used by edge middleware to route / vs /ai.market.intelligence.agent.
 */
export function setAuthCookie(persistent: boolean): void {
  if (typeof document === "undefined") return;
  const maxAge = persistent ? 2592000 : undefined; // 30 days or session
  const secure = window.location.protocol === "https:";
  let cookie = `${AUTH_COOKIE_NAME}=1; path=/; SameSite=Lax`;
  if (maxAge) cookie += `; max-age=${maxAge}`;
  if (secure) cookie += "; Secure";
  document.cookie = cookie;
}

/**
 * Clears the auth cookie on logout or when tokens are cleared.
 */
export function clearAuthCookie(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${AUTH_COOKIE_NAME}=; path=/; max-age=0`;
}
