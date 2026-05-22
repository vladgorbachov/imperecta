// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminPage } from "./AdminPage";

const toastSuccess = vi.fn();
const toastError = vi.fn();

const addMarketplacesMutateAsync = vi.fn();
const runPipelineMutateAsync = vi.fn();

const mockUseAuthStore = vi.fn();
const mockUseAdminStats = vi.fn();
const mockUseParsingTestMarketplaces = vi.fn();
const mockUseParsingTestRuns = vi.fn();
const mockUseAddParsingTestMarketplaces = vi.fn();
const mockUseRunParsingFullTest = vi.fn();
const mockUseParsingJobStatus = vi.fn();

vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}));

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

vi.mock("@/hooks/useAdmin", () => ({
  useAdminStats: () => mockUseAdminStats(),
  useParsingTestMarketplaces: () => mockUseParsingTestMarketplaces(),
  useParsingTestRuns: () => mockUseParsingTestRuns(),
  useAddParsingTestMarketplaces: () => mockUseAddParsingTestMarketplaces(),
  useRunParsingFullTest: () => mockUseRunParsingFullTest(),
  useParsingJobStatus: (jobId: string | null) => mockUseParsingJobStatus(jobId),
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
    mockUseParsingTestMarketplaces.mockReturnValue({
      isLoading: false,
      data: [
        {
          name: "Test Market",
          url: "https://example.com",
          products_in_pool: 120,
          last_successful_scrape: "2026-05-21T10:00:00Z",
          success_rate: 94.2,
          last_run: "2026-05-21T11:00:00Z",
          status: "completed",
        },
      ],
    });
    mockUseParsingTestRuns.mockReturnValue({
      isLoading: false,
      data: [
        {
          job_id: "job-1-uuid",
          started_at: "2026-05-21T11:00:00Z",
          completed_at: "2026-05-21T11:02:00Z",
          duration_seconds: 120,
          listings_created: 22,
          prices_saved: 20,
          errors_count: 1,
          status: "completed",
        },
      ],
    });
    mockUseAddParsingTestMarketplaces.mockReturnValue({
      isPending: false,
      mutateAsync: addMarketplacesMutateAsync.mockResolvedValue({ added: 5, skipped: 0 }),
    });
    mockUseRunParsingFullTest.mockReturnValue({
      isPending: false,
      mutateAsync: runPipelineMutateAsync.mockResolvedValue({
        job_id: "pipeline-job-uuid",
      }),
    });
    mockUseParsingJobStatus.mockImplementation((jobId: string | null) => {
      if (jobId === "job-1-uuid") {
        return {
          isLoading: false,
          data: {
            job_id: "job-1-uuid",
            status: "completed",
            current_stage: "persist",
            started_at: "2026-05-21T11:00:00Z",
            completed_at: "2026-05-21T11:02:00Z",
            duration_seconds: 120,
            metadata: {
              timings: {
                discovery_ms: 1000,
                scrape_ms: 2000,
                persist_ms: 1500,
                total_ms: 4500,
              },
              per_marketplace: [
                {
                  marketplace_id: "mp-1",
                  domain: "example.com",
                  listings_created: 22,
                  prices_saved: 20,
                  errors_count: 1,
                  duration_ms: 900,
                  status: "completed",
                },
              ],
            },
          },
        };
      }
      return {
        isLoading: false,
        data: null,
      };
    });
  });

  it("renders marketplace and run history blocks", () => {
    renderPage();

    expect(screen.getByText("Тестовые маркетплейсы")).toBeInTheDocument();
    expect(screen.getByText("Test Market")).toBeInTheDocument();
    expect(screen.getByText("История тестовых запусков")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /job-1-uu/i })).toBeInTheDocument();
  });

  it("calls add test marketplaces mutation", async () => {
    renderPage();

    fireEvent.click(
      screen.getAllByRole("button", { name: "Добавить 5 тестовых маркетплейсов" })[0],
    );

    await waitFor(() => {
      expect(addMarketplacesMutateAsync).toHaveBeenCalledTimes(1);
    });
  });

  it("calls run full pipeline mutation", async () => {
    renderPage();

    fireEvent.click(
      screen.getAllByRole("button", { name: "Запустить полный цикл тестового парсинга" })[0],
    );

    await waitFor(() => {
      expect(runPipelineMutateAsync).toHaveBeenCalledTimes(1);
    });
  });

  it("opens run details dialog from history row", async () => {
    renderPage();

    const jobButton = screen.getAllByRole("button", { name: /job-1-uu/i })[0];
    const row = jobButton.closest("tr");
    if (!row) {
      throw new Error("Run history row is not found");
    }
    fireEvent.click(row);

    await waitFor(() => {
      expect(screen.getByText("Разбивка времени выполнения и статистика по каждому маркетплейсу.")).toBeInTheDocument();
      expect(screen.getByText("Breakdown времени")).toBeInTheDocument();
      expect(screen.getByText("По маркетплейсам")).toBeInTheDocument();
      expect(screen.getByText("example.com")).toBeInTheDocument();
    });
  });

  it("shows access denied for non-superuser", () => {
    mockUseAuthStore.mockReturnValue({
      user: { is_superuser: false },
    });

    renderPage();

    expect(screen.getByText("Доступ запрещён")).toBeInTheDocument();
  });
});
