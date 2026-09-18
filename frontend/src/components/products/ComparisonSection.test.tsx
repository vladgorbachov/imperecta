// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ComparisonSection } from "./ComparisonSection";

const getListingComparisonMock = vi.fn();

vi.mock("@/api/dataOps", () => ({
  dataOpsApi: {
    getListingComparison: (...args: unknown[]) => getListingComparisonMock(...args),
  },
}));

function renderSection(listingId = "listing-1") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ComparisonSection listingId={listingId} enabled />
    </QueryClientProvider>,
  );
}

const offer = (overrides: Record<string, unknown>) => ({
  listing_id: "listing-x",
  product_id: "product-1",
  marketplace_code: "x-kom_pl",
  marketplace_name: "x-kom",
  country_code: "PL",
  name: "A4Tech BLOODY R73",
  title_en: null,
  external_url: "https://example.com/item",
  last_price: 121.9,
  last_currency_code: "PLN",
  last_price_eur: 27.98,
  last_checked_at: "2026-09-18T10:00:00Z",
  match_method: "brand_model",
  match_confidence: 0.9,
  ...overrides,
});

describe("ComparisonSection", () => {
  afterEach(() => cleanup());
  beforeEach(() => vi.clearAllMocks());

  it("renders offers with the cheapest highlighted and unpriced badged", async () => {
    getListingComparisonMock.mockResolvedValue({
      data: {
        listing_id: "listing-1",
        match_method: "brand_model",
        group: {
          group_id: "group-1",
          shops: 3,
          min_price_eur: 27.98,
          max_price_eur: 34.2,
          offers: [
            offer({ listing_id: "listing-1", last_price_eur: 27.98 }),
            offer({
              listing_id: "listing-2",
              marketplace_name: "Ultra",
              marketplace_code: "ultra_md",
              country_code: "MD",
              last_price_eur: 34.2,
              match_confidence: 0.8,
            }),
            offer({
              listing_id: "listing-3",
              marketplace_name: "Kaspi",
              marketplace_code: "kaspi_kz",
              country_code: "KZ",
              last_price: null,
              last_currency_code: null,
              last_price_eur: null,
            }),
          ],
        },
      },
    });

    renderSection();
    expect(await screen.findByText("comparison.cheapest")).toBeInTheDocument();
    expect(screen.getByText("comparison.current")).toBeInTheDocument();
    expect(screen.getByText("comparison.priceUpdating")).toBeInTheDocument();
    expect(screen.getByText("comparison.possibleMatch")).toBeInTheDocument();
    expect(screen.getByText("comparison.shops")).toBeInTheDocument();
    expect(getListingComparisonMock).toHaveBeenCalledWith("listing-1");
  });

  it("shows the honest pending state when the listing is unmatched", async () => {
    getListingComparisonMock.mockResolvedValue({
      data: { listing_id: "listing-1", match_method: "unmatched", group: null },
    });

    renderSection();
    expect(await screen.findByText("comparison.unavailable")).toBeInTheDocument();
  });
});
