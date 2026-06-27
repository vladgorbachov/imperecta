// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MarketCoverageWidget } from "./MarketCoverageWidget";

const getGeoCoverageMock = vi.fn();

vi.mock("@/api/markets", () => ({
  marketsApi: {
    getGeoCoverage: (...args: unknown[]) => getGeoCoverageMock(...args),
  },
  marketsQueryKeys: {
    geoCoverage: (params?: unknown) => ["markets", "geo-coverage", params],
  },
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { country?: string }) =>
      opts?.country ? `${key}:${opts.country}` : key,
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
      <MarketCoverageWidget
        countryCode={props.countryCode ?? null}
        marketplaceId={props.marketplaceId}
      />
    </QueryClientProvider>,
  );
}

describe("MarketCoverageWidget", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    getGeoCoverageMock.mockResolvedValue({
      data: {
        mode: "countries",
        total: 0,
        rows: [],
      },
    });
  });

  it("shows empty state when roll-up has no rows", async () => {
    renderWidget({ countryCode: null });
    expect(await screen.findByText("market.overview.coverage.empty")).toBeInTheDocument();
    expect(screen.getByText("market.overview.coverage.emptyHint")).toBeInTheDocument();
  });

  it("renders country rows with counts", async () => {
    getGeoCoverageMock.mockResolvedValue({
      data: {
        mode: "countries",
        total: 100,
        rows: [
          {
            key: "LV",
            label: "Latvia",
            country_code: "LV",
            count: 60,
            share_pct: 60,
          },
          {
            key: "LT",
            label: "Lithuania",
            country_code: "LT",
            count: 40,
            share_pct: 40,
          },
        ],
      },
    });

    renderWidget({ countryCode: null });
    await screen.findByText(/Latvia/i);
    expect(screen.getByText("60")).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument();
  });

  it("requests marketplace breakdown when a country is selected", async () => {
    getGeoCoverageMock.mockResolvedValue({
      data: {
        mode: "marketplaces",
        total: 10,
        rows: [
          {
            key: "mp-1",
            label: "Barbora",
            marketplace_domain: "barbora.lv",
            count: 10,
            share_pct: 100,
          },
        ],
      },
    });

    renderWidget({ countryCode: "LV" });
    await screen.findByText("Barbora");
    expect(getGeoCoverageMock).toHaveBeenCalledWith(
      expect.objectContaining({ country_code: "LV" }),
    );
  });

  it("shows skeleton while loading", () => {
    getGeoCoverageMock.mockReturnValue(new Promise(() => undefined));
    renderWidget({ countryCode: null });
    expect(screen.getByTestId("coverage-skeleton")).toBeInTheDocument();
  });
});
