// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MarketsOverviewSection } from "./MarketsOverviewSection";

const getOverviewMock = vi.fn();
const getPoolMarketplaceStatsMock = vi.fn();
const getPoolStatsMock = vi.fn();

vi.mock("@/api/markets", () => ({
  marketsApi: {
    getOverview: (...args: unknown[]) => getOverviewMock(...args),
    getPoolMarketplaceStats: (...args: unknown[]) => getPoolMarketplaceStatsMock(...args),
    getPoolStats: (...args: unknown[]) => getPoolStatsMock(...args),
  },
  marketsQueryKeys: {
    overview: (params?: unknown) => ["markets", "overview", params],
    poolMarketplaceStats: () => ["markets", "pool-marketplace-stats"],
    poolStats: () => ["markets", "pool-stats"],
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
            current_price: 1200,
            currency: "UAH",
            price_change_pct_24h: 6.2,
            status: "active",
            last_scraped_at: "2026-05-21T10:00:00Z",
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
            current_price: 2000,
            currency: "UAH",
            price_change_pct_24h: -3,
            status: "active",
            last_scraped_at: "2026-05-20T10:00:00Z",
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
  });

  it("renders KPI cards", async () => {
    renderSection();
    await screen.findByText("market.overview.kpi.totalPool");
    expect(screen.getByText("market.overview.kpi.updated24h")).toBeInTheDocument();
    expect(screen.getByText("market.overview.kpi.avgVolatility")).toBeInTheDocument();
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
    expect(screen.getAllByText(/Barbora \(Latvia\)/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Barbora \(Lithuania\)/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Store Beta \(Ukraine\)/i).length).toBeGreaterThan(0);
  });
});
