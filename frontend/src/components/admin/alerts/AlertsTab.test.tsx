// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ServiceAlertsPage } from "@/api/admin";
import { AlertsTab } from "./AlertsTab";

const getServiceAlertsMock = vi.fn();

vi.mock("@/hooks/useAdmin", () => ({
  useServiceAlerts: (params: unknown) => {
    const result = getServiceAlertsMock(params);
    return result;
  },
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "en" },
  }),
}));

function makeAlert(
  overrides: Partial<ServiceAlertsPage["items"][number]> = {},
): ServiceAlertsPage["items"][number] {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    alert_class: "service",
    module: "discovery",
    submodule: "fetch_adapter",
    severity: "warning",
    anomaly_type: "fetch_empty_soup_spike",
    message: "Fetch empty soup spike marketplace_id=1",
    context: { empty_rate: 0.9 },
    triggered_at: "2026-06-17T12:00:00+00:00",
    resolved_at: null,
    ...overrides,
  };
}

function mockQueryResult(data: ServiceAlertsPage) {
  return {
    data,
    isLoading: false,
    isError: false,
    isFetching: false,
  };
}

function renderTab() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AlertsTab />
    </QueryClientProvider>,
  );
}

describe("AlertsTab", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    getServiceAlertsMock.mockImplementation((params: { resolved?: string }) => {
      if (params?.resolved === "open" && params?.limit === 1) {
        return mockQueryResult({ items: [], total: 0, limit: 1, offset: 0 });
      }
      return mockQueryResult({ items: [], total: 0, limit: 50, offset: 0 });
    });
  });

  it("shows all-clear empty state when no alerts", async () => {
    renderTab();
    expect(await screen.findByText("admin.alerts.empty")).toBeInTheDocument();
    expect(screen.getByText("admin.alerts.emptyHint")).toBeInTheDocument();
  });

  it("renders alert rows with severity and message", async () => {
    getServiceAlertsMock.mockImplementation((params: { resolved?: string; limit?: number }) => {
      if (params?.resolved === "open" && params?.limit === 1) {
        return mockQueryResult({ items: [], total: 1, limit: 1, offset: 0 });
      }
      return mockQueryResult({
        items: [
          makeAlert(),
          makeAlert({
            id: "00000000-0000-0000-0000-000000000002",
            severity: "critical",
            submodule: "classifier_adapter",
            anomaly_type: "classify_unknown_rate_high",
            message: "Classify unknown rate high",
          }),
        ],
        total: 2,
        limit: 50,
        offset: 0,
      });
    });

    renderTab();
    expect(await screen.findByText("Fetch empty soup spike marketplace_id=1")).toBeInTheDocument();
    expect(screen.getByText("Classify unknown rate high")).toBeInTheDocument();
    expect(screen.getAllByText("admin.alerts.severity.warning").length).toBeGreaterThan(0);
    expect(screen.getAllByText("admin.alerts.severity.critical").length).toBeGreaterThan(0);
  });

  it("expands row to show context json", async () => {
    getServiceAlertsMock.mockImplementation((params: { limit?: number }) => {
      if (params?.limit === 1) {
        return mockQueryResult({ items: [], total: 1, limit: 1, offset: 0 });
      }
      return mockQueryResult({
        items: [makeAlert()],
        total: 1,
        limit: 50,
        offset: 0,
      });
    });

    renderTab();
    const rowButton = await screen.findByRole("button", {
      name: /Fetch empty soup spike/i,
    });
    fireEvent.click(rowButton);
    expect(await screen.findByText("empty_rate")).toBeInTheDocument();
    expect(screen.getByText("0.9")).toBeInTheDocument();
  });

  it("wires resolved filter to query params", async () => {
    renderTab();
    await screen.findByText("admin.alerts.empty");
    fireEvent.click(screen.getByRole("button", { name: "admin.alerts.resolved" }));
    await waitFor(() => {
      expect(getServiceAlertsMock).toHaveBeenCalledWith(
        expect.objectContaining({ resolved: "resolved", module: "discovery" }),
      );
    });
  });
});
