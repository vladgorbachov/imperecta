/**
 * App root with routing.
 *
 * i18n keys by component:
 *
 * common: save, cancel, delete, loading, error, back, next, search, noData, confirm, close,
 *   add, edit, actions, status, date, price, name, comingSoon, underDevelopment, currency,
 *   dash, copy, copied, notFound, backToMarkets
 *
 * nav: dashboard, products, competitors, alerts, digests, import, settings, logo
 *
 * auth: login, loginTitle, register, registerTitle, logout, profile, email, password, name,
 *   companyName, submitLogin, submitRegister, rememberMe, forgotPassword, or, noAccount,
 *   hasAccount, login.description, register.description, emailPlaceholder, loginError,
 *   register.language, registerError, confirmPassword, emailInvalid, fieldRequired,
 *   passwordMismatch, passwordWeak, passwordMedium, passwordStrong, tagline, feature1,
 *   feature2, feature3, forgotPasswordTitle, forgotPasswordComingSoon
 *
 * dashboard: products, competitors, alertsToday, priceChanges, topChanges, topChangesToday,
 *   updatedAgo, showAll, activePromos, anomalies, anomaliesEmpty, weeklyChart, product,
 *   competitor, was, became, change, noData
 *
 * products: search, category, addProduct, importCsv, name, sku, myPrice, minCompetitorPrice,
 *   maxPrice, competitorCount, lastParsing, overpriced, allCategories, urlPlaceholder,
 *   addSuccess, addError, fillNameAndPrice, paginationCount, paginationShown, noProducts,
 *   noProductsHint, noResults, clearFilters, position, overpricedBy, cheaperBy, add
 *
 * productDetail: priceChart, competitors, alerts, createAlert, period7d, period30d, period90d,
 *   myPrice, trendUp, trendDown, trendStable, inStock, outOfStock, diffPercent, promo, stock,
 *   myPriceLegend, runParsing, parseSuccess, parsePending
 *
 * competitors: addCompetitor, linkProduct, name, websiteUrl, marketplace, product, productUrl,
 *   scraper, selectProduct, added, myProduct, autoDetect, scraperAuto, scraperUniversal,
 *   scraperJsonApi, scraperGeneric, noCompetitors, noProductsLinked, addSuccess, addError,
 *   linkSuccess, linkError, linkTo, productsCount, productsCountHeader, tableProduct, tableUrl,
 *   tablePrice, tableLastChecked
 *
 * alerts: createAlert, createRule, activeRules, recentEvents, eventHistory, eventHistoryEmpty,
 *   eventHistoryEmptyHint, noAlerts, noAlertsHint, noEvents, type, product, threshold, channel,
 *   status, on, off, allProducts, create, createSuccess, createError, deleteConfirm,
 *   deleteConfirmDesc, thresholdPlaceholder, typePriceDrop, typePriceIncrease, typeOutOfStock,
 *   typeNewPromo, channelEmail, channelTelegram, channelBoth, date, change, sentVia
 *
 * digests: noDigests, dailyDigest, weeklyDigest, typeDaily, typeWeekly, created, sent, draft,
 *   view, resend, emptyTitle, emptyHint
 *
 * import: uploadTitle, uploadDescription, dropzone, dropzoneCsv, or, selectFile, changeFile,
 *   ignore, downloadTemplate, previewTitle, resultTitle, imported, errors, importing, importBtn,
 *   importProducts, importMore, success, error, errorsCount, parseError, fileFormatError,
 *   rowError, previewName, previewSku, previewPrice, previewUrl, previewCategory,
 *   columnName, columnSku, columnPrice, columnUrl, columnCategory, resultSummary
 *
 * settings: profile, profileDescription, telegram, telegramDescription,
 *   telegramConnected, telegramDisconnected, telegramDisconnect, telegramDisconnectedSuccess,
 *   getLinkCode, codeInstruction, getCodeInstruction, notifications, notificationsDescription,
 *   channelEmail, channelTelegram, channelBoth, digestTime, digestTimeComingSoon, plan,
 *   planDescription, planTrial, planBasic, planPro, trialWarning, trialEnds, productsLimit,
 *   competitorsLimit, upgradePlan, upgradeComingSoon
 *
 * layout: navigation, defaultCompany, trialDaysLeft, upgrade
 *
 * ui: trendPercentPositive, trendPercentNegative, trendPercentZero, priceChangeArrow,
 *   promo, discount, outOfStock, new
 */

import { Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { AuthProvider } from "@/components/auth/AuthProvider";
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
import { ProductDetailPage } from "@/pages/ProductDetailPage";
import { DigestsPage } from "@/pages/DigestsPage";
import { ImportPage } from "@/pages/ImportPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { AdminPage } from "@/pages/AdminPage";
import { AnalyticsPage } from "@/pages/AnalyticsPage";
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
      <AuthProvider>
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
                    <Route path="products/:id" element={<ProductDetailPage />} />
                    <Route path="digests" element={<DigestsPage />} />
                    <Route path="import" element={<ImportPage />} />
                    <Route path="analytics" element={<AnalyticsPage />} />
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
      </AuthProvider>
    </QueryClientProvider>
  );
}
