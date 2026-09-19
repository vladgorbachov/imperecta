// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AdminPage } from "./AdminPage";

const mockUseAuthStore = vi.fn();
vi.mock("@/stores/authStore", () => ({
  useAuthStore: (selector: (state: { user: { is_superuser?: boolean } | null }) => unknown) =>
    selector(mockUseAuthStore()),
}));

vi.mock("@/components/ui-custom/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <div data-testid="page-header">{title}</div>,
}));
vi.mock("@/components/admin/DataCollectionTab", () => ({
  DataCollectionTab: () => <div data-testid="data-collection-tab" />,
}));
vi.mock("@/components/admin/AdminOpsOverview", () => ({
  AdminOpsOverview: () => <div data-testid="ops-tab" />,
}));
vi.mock("@/components/admin/alerts/AlertsTab", () => ({
  AlertsTab: () => <div data-testid="alerts-tab" />,
}));
vi.mock("@/components/admin/compliance/BlockedCountriesSection", () => ({
  BlockedCountriesSection: () => <div data-testid="compliance-section" />,
}));
vi.mock("@/hooks/useAdmin", () => ({
  useAdminStats: () => ({ data: undefined }),
  useParsingMarketplacesDetailed: () => ({ isLoading: false, data: { items: [], total: 0, page: 1, page_size: 20 } }),
  useParsingUsersDetailed: () => ({ isLoading: false, data: [] }),
  useParsingJobStatus: () => ({ isLoading: false, data: null }),
  useCountries: () => ({ isLoading: false, data: [] }),
  useAddMarketplace: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateMarketplace: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteMarketplace: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCreateAdminUser: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateAdminUser: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSetAdminUserStatus: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSetAdminUserRole: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useResetAdminUserPassword: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteAdminUser: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

function renderAdmin(initialPath: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/admin/:tab" element={<AdminPage />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

describe("AdminPage — compliance tab access", () => {
  afterEach(() => cleanup());
  beforeEach(() => vi.clearAllMocks());

  it("renders the Compliance tab and section for a superuser", async () => {
    mockUseAuthStore.mockReturnValue({ user: { is_superuser: true } });
    renderAdmin("/admin/compliance");
    expect(screen.getByRole("tab", { name: "admin.tabs.compliance" })).toBeInTheDocument();
    expect(await screen.findByTestId("compliance-section")).toBeInTheDocument();
  });

  it("hides the whole admin surface, tab included, for non-superusers", () => {
    mockUseAuthStore.mockReturnValue({ user: { is_superuser: false } });
    renderAdmin("/admin/compliance");
    expect(screen.queryByRole("tab", { name: "admin.tabs.compliance" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("compliance-section")).not.toBeInTheDocument();
    expect(screen.getByText("common.error")).toBeInTheDocument();
  });
});
