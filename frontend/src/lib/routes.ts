/**
 * Centralized route policy: public vs private.
 * Used by ProtectedRoute, auth pages, and redirect logic.
 */

/** Paths that do not require authentication. */
export const PUBLIC_ROUTES = [
  "/ai.market.intelligence.agent",
  "/login",
  "/register",
  "/forgot-password",
] as const;

/** Default destination after successful login/register. */
export const DEFAULT_AUTH_RETURN = "/dashboard";

/** Public landing page path. Used for unauthenticated root redirect (dev + edge). */
export const LANDING_PATH = "/ai.market.intelligence.agent";

/** Query param for preserving intended destination. */
export const NEXT_PARAM = "next";

/**
 * Returns true if the path is a public route (no auth required).
 */
export function isPublicRoute(pathname: string): boolean {
  const path = pathname.replace(/\/$/, "") || "/";
  return PUBLIC_ROUTES.some((r) => path === r || path.startsWith(`${r}/`));
}

/**
 * Returns true if the path is a private route (auth required).
 */
export function isPrivateRoute(pathname: string): boolean {
  return !isPublicRoute(pathname);
}

/**
 * Builds login URL with next param for redirect after auth.
 */
export function getLoginUrl(returnPath: string): string {
  const safe = returnPath.startsWith("/") ? returnPath : `/${returnPath}`;
  const encoded = encodeURIComponent(safe);
  return `/login?${NEXT_PARAM}=${encoded}`;
}

/**
 * Extracts return path from URL search params or location state.
 * Priority: next param > state.from > default.
 * Rejects public auth routes (login, register, etc.) to avoid redirect loops.
 */
export function getReturnPath(
  searchParams: URLSearchParams,
  state?: { from?: { pathname: string } } | null
): string {
  const raw = searchParams.get(NEXT_PARAM) ?? state?.from?.pathname;
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) {
    return DEFAULT_AUTH_RETURN;
  }
  const pathname = raw.split("?")[0].split("#")[0];
  if (isPublicRoute(pathname)) {
    return DEFAULT_AUTH_RETURN;
  }
  return raw;
}
