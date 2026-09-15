// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Header } from "./Header";

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

describe("Header", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders theme toggle and notifications controls", () => {
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Header />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("common.toggleTheme")).toBeInTheDocument();
    expect(screen.getByLabelText("common.notifications")).toBeInTheDocument();
  });

  it("does not render the removed market ticker", () => {
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Header />
      </MemoryRouter>,
    );

    expect(screen.queryByTestId("header-ticker")).not.toBeInTheDocument();
  });
});
