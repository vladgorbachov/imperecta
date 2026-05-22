// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MarketsOverviewSection } from "./MarketsOverviewSection";

const createAlertMock = vi.fn();
const createProductMock = vi.fn();
const getOverviewMock = vi.fn();
const getPoolMarketplaceStatsMock = vi.fn();
const getPoolStatsMock = vi.fn();

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/api/alerts", () => ({
  alertsApi: {
    create: (...args: unknown[]) => createAlertMock(...args),
  },
}));

vi.mock("@/api/products", () => ({
  productsApi: {
    create: (...args: unknown[]) => createProductMock(...args),
  },
}));

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

vi.mock("@/components/ui-custom/Sparkline", () => ({
  Sparkline: () => <div data-testid="sparkline-mock" />,
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
            marketplace_name: "Rozetka",
            marketplace_domain: "rozetka.com.ua",
            url: "https://example.com/1",
            title: "Смартфон X",
            image_url: null,
            current_price: 1200,
            currency: "UAH",
            price_change_pct_24h: 6.2,
            status: "active",
            last_scraped_at: "2026-05-21T10:00:00Z",
            recent_prices: [
              { date: "2026-05-15", price: 1000, currency: "UAH" },
              { date: "2026-05-16", price: 1050, currency: "UAH" },
              { date: "2026-05-17", price: 1100, currency: "UAH" },
            ],
          },
          {
            id: "listing-2",
            product_id: "product-2",
            marketplace_id: "market-2",
            marketplace_name: "Prom",
            marketplace_domain: "prom.ua",
            url: "https://example.com/2",
            title: "Ноутбук Y",
            image_url: null,
            current_price: 2000,
            currency: "UAH",
            price_change_pct_24h: -3,
            status: "active",
            last_scraped_at: "2026-05-20T10:00:00Z",
            recent_prices: [
              { date: "2026-05-15", price: 2400, currency: "UAH" },
              { date: "2026-05-16", price: 2300, currency: "UAH" },
            ],
          },
        ],
        total: 2,
        limit: 200,
        offset: 0,
      },
    });
    getPoolMarketplaceStatsMock.mockResolvedValue({
      data: [
        { marketplace_domain: "rozetka.com.ua", marketplace_name: "Rozetka", product_count: 50 },
        { marketplace_domain: "prom.ua", marketplace_name: "Prom", product_count: 40 },
      ],
    });
    getPoolStatsMock.mockResolvedValue({
      data: {
        total_products: 90,
      },
    });
    createAlertMock.mockResolvedValue({ data: { id: "alert-1" } });
    createProductMock.mockResolvedValue({ data: { id: "product-new" } });
  });

  it("renders KPI cards", async () => {
    renderSection();
    await screen.findByText("Всего товаров в пуле");
    expect(screen.getByText("Обновлено за 24ч")).toBeInTheDocument();
    expect(screen.getByText("Товаров с изменением >5%")).toBeInTheDocument();
    expect(screen.getByText("Средняя волатильность пула")).toBeInTheDocument();
    expect(screen.getByText("Последнее обновление")).toBeInTheDocument();
  });

  it("renders table with sparkline and allows switching to cards", async () => {
    renderSection();
    expect((await screen.findAllByRole("cell", { name: "Смартфон X" })).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Sparkline (7д)").length).toBeGreaterThan(0);

    fireEvent.click(screen.getAllByRole("button", { name: /Карточки/i })[0]);
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "В мои товары" }).length).toBeGreaterThan(0);
    });
  });

  it("filters by marketplace and tabs", async () => {
    renderSection();
    expect((await screen.findAllByRole("cell", { name: "Смартфон X" })).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Только с историей цен" }));
    expect(screen.getByRole("button", { name: "Только с историей цен" })).toBeInTheDocument();

    const callsBeforeTab = getOverviewMock.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Растут" }));
    await waitFor(() => {
      expect(getOverviewMock.mock.calls.length).toBeGreaterThan(callsBeforeTab);
    });
  });

  it("creates alert and adds product actions", async () => {
    renderSection();
    expect((await screen.findAllByRole("cell", { name: "Смартфон X" })).length).toBeGreaterThan(0);

    fireEvent.click(screen.getAllByRole("button", { name: /Алерт/i })[0]);
    fireEvent.click(screen.getAllByRole("button", { name: /В мои/i })[0]);

    await waitFor(() => {
      expect(createAlertMock).toHaveBeenCalled();
      expect(createProductMock).toHaveBeenCalled();
    });
  });
});
