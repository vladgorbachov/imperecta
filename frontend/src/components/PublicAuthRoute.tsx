/**
 * Wrapper for public auth pages (login, register, forgot-password).
 * Redirects authenticated users to return path or app root.
 */

import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { getReturnPath } from "@/lib/routes";

interface PublicAuthRouteProps {
  children: React.ReactNode;
}

export function PublicAuthRoute({ children }: PublicAuthRouteProps) {
  const location = useLocation();
  const hasAuth = useAuthStore((s) => !!(s.accessToken ?? s.user));

  if (hasAuth) {
    const returnPath = getReturnPath(
      new URLSearchParams(location.search),
      location.state as { from?: { pathname: string } } | undefined
    );
    return <Navigate to={returnPath} replace />;
  }

  return <>{children}</>;
}
