// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MarketMoversWidget } from "./MarketMoversWidget";

const getMoversMock = vi.fn();

vi.mock("@/api/markets", () => ({
  marketsApi: {
    getMovers: (...args: unknown[]) => getMoversMock(...args),
  },
  marketsQueryKeys: {
    movements: (params?: unknown) => ["markets", "movements", params],
  },
}));

function renderWidget(props: { movementsDataReady: boolean; displayCurrency?: "local" | "EUR" | "USD" }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MarketMoversWidget
        movementsDataReady={props.movementsDataReady}
        displayCurrency={props.displayCurrency ?? "EUR"}
      />
    </QueryClientProvider>,
  );
}

describe("MarketMoversWidget", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    getMoversMock.mockResolvedValue({
      data: {
        items: [],
        total: 0,
        limit: 10,
        offset: 0,
        has_more: false,
      },
    });
  });

  it("renders accumulating state when coverage is not ready", async () => {
    renderWidget({ movementsDataReady: false });
    await screen.findByText("market.overview.kpi.accumulatingData");
    expect(screen.getByText("market.overview.kpi.accumulatingDataHint")).toBeInTheDocument();
  });

  it("renders grouped gainers and losers when data is present", async () => {
    getMoversMock.mockResolvedValue({
      data: {
        items: [
          {
            product_name: "Phone A",
            marketplace_name: "Shop DE",
            marketplace_domain: "shop.de",
            country_code: "DE",
            old_price: "100.00",
            new_price: "120.00",
            currency: "EUR",
            price_change_pct: "20.0",
            direction: "up",
            changed_at: "2026-06-17T12:00:00Z",
            old_price_reconstructed: false,
            display_old_price: "100.00",
            display_new_price: "120.00",
            display_currency: "EUR",
            conversion_available: true,
          },
          {
            product_name: "Laptop B",
            marketplace_name: "Store PL",
            marketplace_domain: "store.pl",
            country_code: "PL",
            old_price: "2000.00",
            new_price: "1800.00",
            currency: "PLN",
            price_change_pct: "-10.0",
            direction: "down",
            changed_at: "2026-06-17T11:00:00Z",
            old_price_reconstructed: true,
            display_old_price: "470.00",
            display_new_price: "423.00",
            display_currency: "EUR",
            conversion_available: true,
          },
        ],
        total: 2,
        limit: 10,
        offset: 0,
        has_more: false,
      },
    });

    renderWidget({ movementsDataReady: true });
    await screen.findByText("market.overview.movements.gainers");
    expect(screen.getByText("market.overview.movements.losers")).toBeInTheDocument();
    expect(screen.getByText("Phone A")).toBeInTheDocument();
    expect(screen.getByText("Laptop B")).toBeInTheDocument();
    expect(getMoversMock).toHaveBeenCalledWith(
      expect.objectContaining({
        period: "24h",
        sort_by: "abs_change",
        threshold: 0,
        direction: "all",
        limit: 10,
        display_currency: "EUR",
      }),
    );
  });

  it("shows accumulating state when movers list is empty", async () => {
    renderWidget({ movementsDataReady: true });
    await screen.findByText("market.overview.kpi.accumulatingData");
  });
});
