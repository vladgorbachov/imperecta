// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AdminPage } from "./AdminPage";

const mockUseAuthStore = vi.fn();
const mockUseAdminStats = vi.fn();
const mockUseParsingMarketplacesDetailed = vi.fn();
const mockUseParsingUsersDetailed = vi.fn();

vi.mock("@/stores/authStore", () => ({
  useAuthStore: (selector: (state: { user: { is_superuser?: boolean } | null }) => unknown) =>
    selector(mockUseAuthStore()),
}));

vi.mock("@/components/ui-custom/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <div data-testid="page-header">{title}</div>,
}));

vi.mock("@/components/ui-custom/EmptyState", () => ({
  EmptyState: ({ title, description }: { title: string; description: string }) => (
    <div>
      <div>{title}</div>
      <div>{description}</div>
    </div>
  ),
}));

vi.mock("@/components/admin/DataCollectionTab", () => ({
  DataCollectionTab: () => <div data-testid="data-collection-tab">data-collection</div>,
}));

vi.mock("@/hooks/useAdmin", () => ({
  useAdminStats: () => mockUseAdminStats(),
  useParsingMarketplacesDetailed: () => mockUseParsingMarketplacesDetailed(),
  useParsingUsersDetailed: () => mockUseParsingUsersDetailed(),
  useParsingJobStatus: () => ({ isLoading: false, data: null }),
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

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AdminPage />
    </QueryClientProvider>,
  );
}

describe("AdminPage parsing section", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();

    mockUseAuthStore.mockReturnValue({
      user: {
        is_superuser: true,
      },
    });
    mockUseAdminStats.mockReturnValue({
      data: { users_count: 12, marketplaces_count: 8, total_products_monitored: 55 },
    });
    mockUseParsingMarketplacesDetailed.mockReturnValue({
      isLoading: false,
      data: {
        items: [
          {
            id: "mp-1",
            marketplace_code: "example_com",
            name: "Test Market",
            domain: "example.com",
            base_url: "https://example.com",
            is_active: true,
            products_in_pool: 10,
            active_listings: 5,
            last_scrape_at: null,
            success_rate: 90,
            last_discovery_at: null,
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    });
    mockUseParsingUsersDetailed.mockReturnValue({
      isLoading: false,
      data: [],
    });
  });

  it("renders data collection tab component", () => {
    renderPage();
    expect(screen.getByTestId("data-collection-tab")).toBeInTheDocument();
  });

  it("renders market overview tab", () => {
    renderPage();
    expect(screen.getByRole("tab", { name: "Market Overview" })).toBeInTheDocument();
    expect(mockUseParsingMarketplacesDetailed).toHaveBeenCalled();
  });

  it("shows access denied for non-superuser", () => {
    mockUseAuthStore.mockReturnValue({
      user: { is_superuser: false },
    });

    renderPage();

    expect(screen.getByText("common.error")).toBeInTheDocument();
  });
});
