// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MarketsOverviewSection } from "./MarketsOverviewSection";

const getOverviewMock = vi.fn();
const getPoolMarketplaceStatsMock = vi.fn();
const getPoolStatsMock = vi.fn();
const getMoversKpiMock = vi.fn();
const getMoversSummaryMock = vi.fn();
const getMoversCoverageMock = vi.fn();
const getMoversMock = vi.fn();
const getDashboardKpiMock = vi.fn();

vi.mock("@/api/markets", () => ({
  marketsApi: {
    getOverview: (...args: unknown[]) => getOverviewMock(...args),
    getPoolMarketplaceStats: (...args: unknown[]) => getPoolMarketplaceStatsMock(...args),
    getPoolStats: (...args: unknown[]) => getPoolStatsMock(...args),
    getDashboardKpi: (...args: unknown[]) => getDashboardKpiMock(...args),
    getMovers: (...args: unknown[]) => getMoversMock(...args),
    getMoversKpi: (...args: unknown[]) => getMoversKpiMock(...args),
    getMoversSummary: (...args: unknown[]) => getMoversSummaryMock(...args),
    getMoversCoverage: (...args: unknown[]) => getMoversCoverageMock(...args),
  },
  marketsQueryKeys: {
    overview: (params?: unknown) => ["markets", "overview", params],
    poolMarketplaceStats: () => ["markets", "pool-marketplace-stats"],
    poolStats: () => ["markets", "pool-stats"],
    dashboardKpi: (params?: unknown) => ["markets", "dashboard-kpi", params],
    movements: (params?: unknown) => ["markets", "movements", params],
    movementsKpi: (params?: unknown) => ["markets", "movements", params, "kpi"],
    movementsSummary: (params?: unknown) => ["markets", "movements", params, "summary"],
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
    getOverviewMock.mockResolvedValue({
      data: {
        items: [
          {
            id: "listing-1",
            product_id: "product-1",
            marketplace_id: "market-1",
            marketplace_name: "Barbora",
            marketplace_domain: "barbora.lv",
            country_code: "LV",
            url: "https://example.com/1",
            title: "Смартфон X",
            image_url: "https://img.example/1.jpg",
            price: 1200,
            currency: "UAH",
            price_change_pct: 6.2,
            status: "active",
            last_checked_at: "2026-05-21T10:00:00Z",
            recent_prices: [
              { date: "2026-05-15", price: 1000, currency: "UAH" },
              { date: "2026-05-16", price: 1050, currency: "UAH" },
            ],
          },
          {
            id: "listing-2",
            product_id: "product-2",
            marketplace_id: "market-2",
            marketplace_name: "Store Beta",
            marketplace_domain: "store-beta.example",
            url: "https://example.com/2",
            title: "Ноутбук Y",
            image_url: null,
            price: 2000,
            currency: "UAH",
            price_change_pct: -3,
            status: "active",
            last_checked_at: "2026-05-20T10:00:00Z",
            recent_prices: [],
          },
        ],
        total: 2,
        limit: 200,
        offset: 0,
      },
    });
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
    getMoversSummaryMock.mockResolvedValue({
      data: {
        up_count: 2,
        down_count: 1,
        unchanged_count: 0,
        biggest_gainer: null,
        biggest_loser: null,
        avg_abs_change: "6.25",
        buckets: [],
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
    expect(getMoversSummaryMock).toHaveBeenCalled();
    expect(getMoversCoverageMock).toHaveBeenCalled();
    expect(getDashboardKpiMock).toHaveBeenCalled();
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
    getMoversSummaryMock.mockResolvedValue({
      data: {
        up_count: 0,
        down_count: 0,
        unchanged_count: 0,
        biggest_gainer: null,
        biggest_loser: null,
        avg_abs_change: null,
        buckets: [],
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

  it("renders product cards with image and external product link", async () => {
    renderSection();
    await screen.findByText("Смартфон X");

    const image = screen.getByAltText("Смартфон X") as HTMLImageElement;
    expect(image.src).toBe("https://img.example/1.jpg");

    const externalLinks = screen
      .getAllByRole("link")
      .filter((link) => link.getAttribute("href") === "https://example.com/1");
    expect(externalLinks.length).toBeGreaterThan(0);
  });

  it("exposes marketplace filters in the side panel", async () => {
    renderSection();
    await screen.findByText("Смартфон X");

    expect(screen.getByText("market.filters.marketplaces")).toBeInTheDocument();
    expect(screen.getAllByText(/Barbora \(LV\)/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Barbora \(LT\)/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Store Beta \(UA\)/i).length).toBeGreaterThan(0);
  });
});
