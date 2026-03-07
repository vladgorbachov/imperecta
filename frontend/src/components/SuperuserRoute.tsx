import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";

interface SuperuserRouteProps {
  children: React.ReactNode;
}

/**
 * Protects admin routes: requires auth and superuser role.
 * Not logged in -> /login
 * Logged in but not superuser -> /dashboard
 */
export function SuperuserRoute({ children }: SuperuserRouteProps) {
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
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (user?.force_password_change) {
    return <Navigate to="/change-password" replace />;
  }

  if (!user?.is_superuser) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
