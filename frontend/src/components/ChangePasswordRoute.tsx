import { Navigate } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { ForcePasswordChangePage } from "@/pages/ForcePasswordChangePage";

/**
 * Route for /change-password: requires auth and force_password_change.
 * Not logged in -> /login
 * Logged in but force_password_change=false -> /dashboard (already changed)
 */
export function ChangePasswordRoute() {
  const { isInitialized, user, accessToken } = useAuthStore();

  if (!isInitialized) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!accessToken) {
    return <Navigate to="/login" replace />;
  }

  if (!user?.force_password_change) {
    return <Navigate to="/dashboard" replace />;
  }

  return <ForcePasswordChangePage />;
}
