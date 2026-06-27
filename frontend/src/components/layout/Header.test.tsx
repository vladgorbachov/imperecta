// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Header } from "./Header";
import { useDashboardCountryStore } from "@/stores/dashboardCountryStore";

vi.mock("next-themes", () => ({
  useTheme: () => ({
    resolvedTheme: "dark",
    setTheme: vi.fn(),
  }),
}));

vi.mock("@/stores/authStore", () => ({
  useAuthStore: () => ({
    user: { name: "Test User", email: "test@example.com" },
    logout: vi.fn(),
  }),
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("./HeaderTicker", () => ({
  HeaderTicker: ({ className }: { className?: string }) => (
    <div data-testid="header-ticker" className={className} />
  ),
}));

describe("Header dashboard country selector", () => {
  afterEach(() => {
    cleanup();
    useDashboardCountryStore.setState({
      selectedCountry: null,
      countryOptions: [],
      optionsLoading: false,
    });
  });

  it("renders country selector on the dashboard route", () => {
    useDashboardCountryStore.setState({
      countryOptions: [{ code: "LV", label: "Latvia" }],
      optionsLoading: false,
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Header />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("markets.countrySelector.placeholder")).toBeInTheDocument();
  });

  it("hides country selector outside the dashboard route", () => {
    render(
      <MemoryRouter initialEntries={["/products"]}>
        <Header />
      </MemoryRouter>,
    );

    expect(screen.queryByLabelText("markets.countrySelector.placeholder")).not.toBeInTheDocument();
  });

  it("keeps ticker full width without artificial max-width cap", () => {
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Header />
      </MemoryRouter>,
    );

    const tickerClass = screen.getByTestId("header-ticker").className;
    expect(tickerClass).not.toMatch(/max-w-/);
    expect(tickerClass).toMatch(/flex-1/);
  });
});
