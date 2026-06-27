// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CountrySelector } from "./CountrySelector";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "en" },
  }),
}));

describe("CountrySelector", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows only the All option when options are empty", () => {
    render(
      <CountrySelector value={null} onChange={vi.fn()} options={[]} loading={false} />,
    );
    expect(screen.getByText("markets.countrySelector.all")).toBeInTheDocument();
  });

  it("renders selected country in the trigger", () => {
    render(
      <CountrySelector
        value="LV"
        onChange={vi.fn()}
        options={[
          { code: "LV", label: "Latvia" },
          { code: "LT", label: "Lithuania" },
        ]}
        loading={false}
      />,
    );
    expect(screen.getByText(/Latvia/i)).toBeInTheDocument();
  });

  it("shows skeleton while loading", () => {
    render(
      <CountrySelector value={null} onChange={vi.fn()} options={[]} loading />,
    );
    expect(screen.getByTestId("country-selector-skeleton")).toBeInTheDocument();
  });
});
