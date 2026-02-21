import { Routes, Route, Navigate } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ProductsPage } from "./pages/ProductsPage";
import { ProductDetailPage } from "./pages/ProductDetailPage";
import { CompetitorsPage } from "./pages/CompetitorsPage";
import { AlertsPage } from "./pages/AlertsPage";
import { DigestsPage } from "./pages/DigestsPage";
import { ImportPage } from "./pages/ImportPage";
import { SettingsPage } from "./pages/SettingsPage";
import { DashboardLayout } from "./components/layout/DashboardLayout";

export const routes = (
  <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route path="/" element={<DashboardLayout />}>
      <Route index element={<Navigate to="/dashboard" replace />} />
      <Route path="dashboard" element={<DashboardPage />} />
      <Route path="products" element={<ProductsPage />} />
      <Route path="products/:id" element={<ProductDetailPage />} />
      <Route path="competitors" element={<CompetitorsPage />} />
      <Route path="alerts" element={<AlertsPage />} />
      <Route path="digests" element={<DigestsPage />} />
      <Route path="import" element={<ImportPage />} />
      <Route path="settings" element={<SettingsPage />} />
    </Route>
  </Routes>
);
