import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { getLoginUrl, LANDING_PATH } from "@/lib/routes";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const location = useLocation();
  const { isInitialized, user, accessToken } = useAuthStore();

  if (!isInitialized) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!accessToken) {
    const pathname = location.pathname.replace(/\/$/, "") || "/";
    if (pathname === "/") {
      return <Navigate to={LANDING_PATH} replace />;
    }
    return <Navigate to={getLoginUrl(location.pathname + location.search)} replace />;
  }

  if (user?.force_password_change) {
    return <Navigate to="/change-password" replace />;
  }

  return <>{children}</>;
}
