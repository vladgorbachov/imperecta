// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MarketTrendWidget } from "./MarketTrendWidget";

const getTrendMock = vi.fn();

vi.mock("@/api/markets", () => ({
  marketsApi: {
    getTrend: (...args: unknown[]) => getTrendMock(...args),
  },
  marketsQueryKeys: {
    trend: (params?: unknown) => ["markets", "trend", params],
  },
}));

vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { count?: number }) => {
      if (opts?.count != null) {
        return `${key}:${opts.count}`;
      }
      return key;
    },
    i18n: { language: "en" },
  }),
}));

function renderWidget(props: { countryCode?: string | null; marketplaceId?: string }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MarketTrendWidget
        countryCode={props.countryCode ?? null}
        marketplaceId={props.marketplaceId}
      />
    </QueryClientProvider>,
  );
}

const readyPoints = [
  {
    bucket_label: "2026-06-01",
    bucket_start: "2026-06-01T00:00:00Z",
    avg_price_eur: "10.50",
    sample_size: 5,
  },
  {
    bucket_label: "2026-06-02",
    bucket_start: "2026-06-02T00:00:00Z",
    avg_price_eur: "11.00",
    sample_size: 8,
  },
];

describe("MarketTrendWidget", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    getTrendMock.mockResolvedValue({
      data: {
        points: [],
        currency: "EUR",
        bucket: "day",
        period: "30d",
        data_ready: false,
      },
    });
  });

  it("renders accumulating state when data is not ready", async () => {
    renderWidget({ countryCode: null });
    expect(await screen.findByText("market.overview.trend.empty")).toBeInTheDocument();
    expect(screen.getByText("market.overview.trend.emptyHint")).toBeInTheDocument();
    expect(screen.queryByTestId("trend-chart")).not.toBeInTheDocument();
  });

  it("renders chart when at least two plottable points exist", async () => {
    getTrendMock.mockResolvedValue({
      data: {
        points: readyPoints,
        currency: "EUR",
        bucket: "day",
        period: "30d",
        data_ready: true,
      },
    });

    renderWidget({ countryCode: null });
    expect(await screen.findByTestId("trend-chart")).toBeInTheDocument();
    expect(screen.queryByText("market.overview.trend.empty")).not.toBeInTheDocument();
  });

  it("shows accumulating state for a single plottable point", async () => {
    getTrendMock.mockResolvedValue({
      data: {
        points: [readyPoints[0]],
        currency: "EUR",
        bucket: "day",
        period: "30d",
        data_ready: true,
      },
    });

    renderWidget({ countryCode: null });
    expect(await screen.findByText("market.overview.trend.empty")).toBeInTheDocument();
    expect(screen.queryByTestId("trend-chart")).not.toBeInTheDocument();
  });

  it("scopes trend query to selected country", async () => {
    getTrendMock.mockResolvedValue({
      data: {
        points: readyPoints,
        currency: "EUR",
        bucket: "day",
        period: "30d",
        data_ready: true,
      },
    });

    renderWidget({ countryCode: "LV" });
    await screen.findByTestId("trend-chart");
    expect(getTrendMock).toHaveBeenCalledWith(
      expect.objectContaining({ country_code: "LV", period: "30d", bucket: "day" }),
    );
  });

  it("shows skeleton while loading", () => {
    getTrendMock.mockReturnValue(new Promise(() => undefined));
    renderWidget({ countryCode: null });
    expect(screen.getByTestId("trend-skeleton")).toBeInTheDocument();
  });
});
