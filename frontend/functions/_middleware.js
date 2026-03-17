/**
 * Cloudflare Pages edge middleware for Imperecta.
 * Routes traffic based on auth cookie presence.
 *
 * Rules:
 * - / + no auth cookie -> redirect to /ai.market.intelligence.agent
 * - / + auth cookie -> pass through (app/dashboard)
 * - /ai.market.intelligence.agent + auth cookie -> redirect to /
 * - /ai.market.intelligence.agent + no auth cookie -> pass through (landing)
 * - All other paths -> pass through
 */

const AUTH_COOKIE_NAME = "imperecta_auth";

function hasAuthCookie(request) {
  const cookieHeader = request.headers.get("Cookie");
  if (!cookieHeader) return false;
  const cookies = cookieHeader.split(";").map((c) => c.trim());
  const prefix = `${AUTH_COOKIE_NAME}=`;
  return cookies.some((c) => c.startsWith(prefix) && c.length > prefix.length);
}

function getPathname(url) {
  try {
    return new URL(url).pathname;
  } catch {
    return "/";
  }
}

export async function onRequest(context) {
  const pathname = getPathname(context.request.url);
  const authenticated = hasAuthCookie(context.request);

  // Exact root: redirect unauthenticated to landing
  if (pathname === "/" || pathname === "") {
    if (!authenticated) {
      return Response.redirect(new URL("/ai.market.intelligence.agent", context.request.url), 302);
    }
    return context.next();
  }

  // Landing route: redirect authenticated to app root
  if (pathname === "/ai.market.intelligence.agent" || pathname === "/ai.market.intelligence.agent/") {
    if (authenticated) {
      return Response.redirect(new URL("/", context.request.url), 302);
    }
    return context.next();
  }

  return context.next();
}
