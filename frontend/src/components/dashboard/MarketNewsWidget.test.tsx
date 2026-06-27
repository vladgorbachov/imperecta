// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MarketNewsWidget } from "./MarketNewsWidget";

const getNewsMock = vi.fn();

vi.mock("@/api/news", () => ({
  newsApi: {
    getNews: (...args: unknown[]) => getNewsMock(...args),
  },
  newsQueryKeys: {
    news: (params?: unknown) => ["news", params],
  },
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "en" },
  }),
}));

function renderWidget(countryCode: string | null = null) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MarketNewsWidget countryCode={countryCode} />
    </QueryClientProvider>,
  );
}

describe("MarketNewsWidget", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    getNewsMock.mockResolvedValue({
      data: {
        items: [],
        source_provider: "none",
      },
    });
  });

  it("renders news items from API", async () => {
    getNewsMock.mockResolvedValue({
      data: {
        items: [
          {
            title: "Retail chain expands in Baltics",
            source: "Retail Week",
            published_at: "2026-06-20T10:00:00Z",
            snippet: "A major EU retailer announced new store openings.",
            url: "https://example.com/article-1",
            image_url: "https://example.com/img.jpg",
          },
        ],
        source_provider: "newsdata",
      },
    });

    renderWidget();
    expect(await screen.findByText("Retail chain expands in Baltics")).toBeInTheDocument();
    expect(screen.getByText("Retail Week")).toBeInTheDocument();
    expect(screen.getByText("A major EU retailer announced new store openings.")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Retail chain expands in Baltics" });
    expect(link).toHaveAttribute("href", "https://example.com/article-1");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("shows unavailable empty state when API returns no items", async () => {
    renderWidget();
    expect(await screen.findByText("market.news.unavailable")).toBeInTheDocument();
    expect(screen.getByText("market.news.unavailableHint")).toBeInTheDocument();
  });

  it("shows skeleton while loading", () => {
    getNewsMock.mockReturnValue(new Promise(() => undefined));
    renderWidget();
    expect(screen.getByTestId("news-skeleton")).toBeInTheDocument();
  });

  it("passes country_code when a country is selected", async () => {
    getNewsMock.mockResolvedValue({
      data: { items: [], source_provider: "none" },
    });
    renderWidget("DE");
    await screen.findByText("market.news.unavailable");
    expect(getNewsMock).toHaveBeenCalledWith(
      expect.objectContaining({ country_code: "DE", language: "en" }),
    );
  });

  it("shows load error on network failure", async () => {
    getNewsMock.mockRejectedValue(new Error("network"));
    renderWidget();
    expect(await screen.findByText("market.news.loadError")).toBeInTheDocument();
  });

  it("cleans noisy source strings for display", async () => {
    getNewsMock.mockResolvedValue({
      data: {
        items: [
          {
            title: "Retail headline",
            source: "Retail Week; Feedloaderapi; Retail Week",
            published_at: "2026-06-20T10:00:00Z",
            snippet: "Snippet text.",
            url: "https://example.com/article-2",
            image_url: null,
          },
        ],
        source_provider: "currents",
      },
    });

    renderWidget();
    expect(await screen.findByText("Retail Week")).toBeInTheDocument();
    expect(screen.queryByText(/Feedloaderapi/i)).not.toBeInTheDocument();
  });

  it("omits unknown source and keeps relative time", async () => {
    getNewsMock.mockResolvedValue({
      data: {
        items: [
          {
            title: "Headline only source",
            source: "unknown",
            published_at: "2026-06-20T10:00:00Z",
            snippet: "Snippet.",
            url: "https://example.com/article-3",
            image_url: null,
          },
        ],
        source_provider: "currents",
      },
    });

    renderWidget();
    expect(await screen.findByText("Headline only source")).toBeInTheDocument();
    expect(screen.queryByText("unknown")).not.toBeInTheDocument();
  });
});
