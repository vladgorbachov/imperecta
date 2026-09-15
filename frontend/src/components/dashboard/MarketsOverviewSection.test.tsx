// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MarketsOverviewSection } from "./MarketsOverviewSection";

const getPoolMarketplaceStatsMock = vi.fn();
const getPoolStatsMock = vi.fn();
const getMoversKpiMock = vi.fn();
const getVolatilityMock = vi.fn();
const getKpiHistoryMock = vi.fn();
const getMoversCoverageMock = vi.fn();
const getMoversMock = vi.fn();
const getDashboardKpiMock = vi.fn();
const getGeoCoverageMock = vi.fn();
const getTrendMock = vi.fn();
const getNewsMock = vi.fn();

vi.mock("@/api/news", () => ({
  newsApi: {
    getNews: (...args: unknown[]) => getNewsMock(...args),
  },
  newsQueryKeys: {
    news: (params?: unknown) => ["news", params],
  },
}));

vi.mock("@/api/markets", () => ({
  marketsApi: {
    getPoolMarketplaceStats: (...args: unknown[]) => getPoolMarketplaceStatsMock(...args),
    getPoolStats: (...args: unknown[]) => getPoolStatsMock(...args),
    getDashboardKpi: (...args: unknown[]) => getDashboardKpiMock(...args),
    getGeoCoverage: (...args: unknown[]) => getGeoCoverageMock(...args),
    getTrend: (...args: unknown[]) => getTrendMock(...args),
    getMovers: (...args: unknown[]) => getMoversMock(...args),
    getMoversKpi: (...args: unknown[]) => getMoversKpiMock(...args),
    getMoversCoverage: (...args: unknown[]) => getMoversCoverageMock(...args),
    getVolatility: (...args: unknown[]) => getVolatilityMock(...args),
    getKpiHistory: (...args: unknown[]) => getKpiHistoryMock(...args),
  },
  marketsQueryKeys: {
    poolMarketplaceStats: () => ["markets", "pool-marketplace-stats"],
    kpiHistory: (params?: unknown) => ["markets", "kpi-history", params],
    volatility: (params?: unknown) => ["markets", "volatility", params],
    poolStats: () => ["markets", "pool-stats"],
    dashboardKpi: (params?: unknown) => ["markets", "dashboard-kpi", params],
    geoCoverage: (params?: unknown) => ["markets", "geo-coverage", params],
    trend: (params?: unknown) => ["markets", "trend", params],
    movements: (params?: unknown) => ["markets", "movements", params],
    movementsKpi: (params?: unknown) => ["markets", "movements", params, "kpi"],
    movementsCoverage: (params?: unknown) => ["markets", "movements", params, "coverage"],
  },
}));

function renderSection() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <MarketsOverviewSection />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("MarketsOverviewSection", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    getPoolMarketplaceStatsMock.mockResolvedValue({
      data: [
        {
          marketplace_domain: "barbora.lv",
          marketplace_name: "Barbora",
          country_code: "LV",
          product_count: 50,
        },
        {
          marketplace_domain: "barbora.lt",
          marketplace_name: "Barbora",
          country_code: "LT",
          product_count: 40,
        },
        {
          marketplace_domain: "store-beta.example",
          marketplace_name: "Store Beta",
          country_code: "UA",
          product_count: 30,
        },
      ],
    });
    getPoolStatsMock.mockResolvedValue({
      data: {
        total_products: 90,
      },
    });
    getMoversKpiMock.mockResolvedValue({ data: { count: 4 } });
    getVolatilityMock.mockResolvedValue({
      data: {
        avg_volatility_pct: 6.25,
        listings_covered: 10,
        window_days: 30,
        period: "30d",
        data_ready: true,
      },
    });
    getKpiHistoryMock.mockResolvedValue({
      data: {
        days: 7,
        series: {
          total_pool: [],
          updated_24h: [],
          changed_gt5: [],
          avg_volatility: [],
        },
      },
    });
    getMoversCoverageMock.mockResolvedValue({
      data: {
        listings_with_change: 12,
        listings_total: 90,
        data_ready: true,
      },
    });
    getMoversMock.mockResolvedValue({
      data: {
        items: [],
        total: 0,
        limit: 10,
        offset: 0,
        has_more: false,
      },
    });
    getDashboardKpiMock.mockResolvedValue({
      data: {
        updated_24h: 12,
        last_update: "2026-05-21T10:00:00Z",
      },
    });
    getGeoCoverageMock.mockResolvedValue({
      data: {
        mode: "countries",
        total: 0,
        rows: [],
      },
    });
    getTrendMock.mockResolvedValue({
      data: {
        points: [],
        currency: "EUR",
        bucket: "day",
        period: "30d",
        data_ready: false,
      },
    });
    getNewsMock.mockResolvedValue({
      data: {
        items: [],
        source_provider: "none",
      },
    });
  });

  it("renders KPI cards from movements endpoints", async () => {
    renderSection();
    await screen.findByText("market.overview.kpi.totalPool");
    expect(screen.getByText("market.overview.kpi.updated24h")).toBeInTheDocument();
    expect(screen.getByText("market.overview.kpi.avgVolatility")).toBeInTheDocument();
    expect(await screen.findByText("4")).toBeInTheDocument();
    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(screen.getByText("6.25%")).toBeInTheDocument();
    expect(getMoversKpiMock).toHaveBeenCalled();
    expect(getVolatilityMock).toHaveBeenCalled();
    expect(getMoversCoverageMock).toHaveBeenCalled();
    expect(getDashboardKpiMock).toHaveBeenCalled();
    expect(getGeoCoverageMock).toHaveBeenCalled();
    expect(screen.getByTestId("market-news-widget")).toBeInTheDocument();
    expect(screen.queryByText("markets.analytics.categoryOverview")).not.toBeInTheDocument();
  });

  it("renders dashboard KPI empty state from server", async () => {
    getDashboardKpiMock.mockResolvedValue({
      data: {
        updated_24h: 0,
        last_update: null,
      },
    });

    renderSection();
    await screen.findByText("market.overview.kpi.updated24h");
    expect(await screen.findByText("0")).toBeInTheDocument();
    const dashValues = screen.getAllByText("common.dash");
    expect(dashValues.length).toBeGreaterThanOrEqual(1);
  });

  it("shows dashboard KPI error state with retry", async () => {
    getDashboardKpiMock.mockRejectedValue(new Error("dashboard kpi failed"));

    renderSection();
    await screen.findByText("market.overview.kpi.updated24h");
    await waitFor(() => {
      expect(screen.getAllByTitle("common.error").length).toBeGreaterThanOrEqual(2);
    });
  });

  it("shows accumulating data state when coverage is not ready", async () => {
    getMoversCoverageMock.mockResolvedValue({
      data: {
        listings_with_change: 0,
        listings_total: 10,
        data_ready: false,
      },
    });
    getMoversKpiMock.mockResolvedValue({ data: { count: 0 } });
    getVolatilityMock.mockResolvedValue({
      data: {
        avg_volatility_pct: null,
        listings_covered: 0,
        window_days: 30,
        period: "30d",
        data_ready: false,
      },
    });

    renderSection();
    await screen.findByText("market.overview.movements.title");
    await waitFor(() => {
      expect(screen.getAllByText("market.overview.kpi.accumulatingData").length).toBeGreaterThanOrEqual(
        2,
      );
    });
    expect(screen.getByText("market.overview.kpi.accumulatingDataHint")).toBeInTheDocument();
    expect(screen.queryByText("0.00%")).not.toBeInTheDocument();
  });

  it("does not render the catalog on the dashboard (moved to Products)", async () => {
    renderSection();
    await screen.findByText("market.overview.kpi.totalPool");

    expect(screen.queryByText("market.filters.marketplaces")).not.toBeInTheDocument();
    expect(screen.queryByText("Смартфон X")).not.toBeInTheDocument();
  });
});
