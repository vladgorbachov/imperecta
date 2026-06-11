/**
 * App root with routing.
 *
 * Live routes (FE1):
 *   public:      /login, /register, /forgot-password, /
 *   protected:   /change-password
 *   layout:      /app/* -> DashboardLayout with nested:
 *                  dashboard, products, digests, settings, ai, admin (superuser).
 *   not-found:   * -> NotFoundPage
 *
 * i18n keys live in src/i18n/locales/*.json — see FE4 for inventory.
 */

import { Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "sonner";
import { LoadingScreen } from "@/components/LoadingScreen";
import { LoginPage } from "@/pages/auth/LoginPage";
import { RegisterPage } from "@/pages/auth/RegisterPage";
import { ForgotPasswordPage } from "@/pages/auth/ForgotPasswordPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ProductsPage } from "@/pages/ProductsPage";
import { DigestsPage } from "@/pages/DigestsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { AdminPage } from "@/pages/AdminPage";
import { AIAnalystRoute } from "@/components/AIAnalystRoute";
import { ChangePasswordRoute } from "@/components/ChangePasswordRoute";
import { PublicAuthRoute } from "@/components/PublicAuthRoute";
import { SuperuserRoute } from "@/components/SuperuserRoute";
import { LandingPage } from "@/pages/landing/LandingPage";
import { useAuthStore } from "@/stores/authStore";

const queryClient = new QueryClient();

/** Redirects authenticated users from landing to app root. */
function LandingRoute({ children }: { children: React.ReactNode }) {
  const hasAuth = useAuthStore((s) => !!(s.accessToken ?? s.user));
  if (hasAuth) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          <TooltipProvider delayDuration={300}>
            <Suspense fallback={<LoadingScreen />}>
              <BrowserRouter>
                <Routes>
                  <Route
                    path="/ai.market.intelligence.agent"
                    element={
                      <LandingRoute>
                        <LandingPage />
                      </LandingRoute>
                    }
                  />
                  <Route
                    path="/login"
                    element={
                      <PublicAuthRoute>
                        <LoginPage />
                      </PublicAuthRoute>
                    }
                  />
                  <Route
                    path="/register"
                    element={
                      <PublicAuthRoute>
                        <RegisterPage />
                      </PublicAuthRoute>
                    }
                  />
                  <Route
                    path="/forgot-password"
                    element={
                      <PublicAuthRoute>
                        <ForgotPasswordPage />
                      </PublicAuthRoute>
                    }
                  />
                  <Route path="/change-password" element={<ChangePasswordRoute />} />
                  <Route
                    path="/"
                    element={
                      <ProtectedRoute>
                        <DashboardLayout />
                      </ProtectedRoute>
                    }
                  >
                    <Route index element={<Navigate to="/dashboard" replace />} />
                    <Route path="dashboard" element={<DashboardPage />} />
                    <Route path="products" element={<ProductsPage />} />
                    <Route path="digests" element={<DigestsPage />} />
                    <Route path="ai" element={<AIAnalystRoute />} />
                    <Route path="settings" element={<SettingsPage />} />
                  </Route>
                  <Route
                    path="/admin"
                    element={
                      <SuperuserRoute>
                        <DashboardLayout />
                      </SuperuserRoute>
                    }
                  >
                    <Route index element={<AdminPage />} />
                  </Route>
                  <Route path="*" element={<NotFoundPage />} />
                </Routes>
                <Toaster
          position="top-center"
          richColors
          closeButton
          toastOptions={{
            classNames: {
              toast: "imperecta-sonner-toast",
              content: "imperecta-sonner-content",
              title: "imperecta-sonner-title",
              icon: "imperecta-sonner-icon",
              closeButton: "imperecta-sonner-close",
            },
            style: {
              background: "var(--background-elevated)",
              border: "1px solid var(--glass-border)",
              backdropFilter: "blur(16px)",
              color: "var(--foreground)",
            },
          }}
        />
              </BrowserRouter>
            </Suspense>
          </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
