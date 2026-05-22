// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Sparkline } from "./Sparkline";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="sparkline-container">{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <svg data-testid="sparkline-chart">{children}</svg>,
  Line: () => <path data-testid="sparkline-line" />,
  Tooltip: () => null,
}));

describe("Sparkline", () => {
  it("renders empty state without enough points", () => {
    render(<Sparkline points={[{ date: "2026-05-01", price: 100 }]} />);
    expect(screen.getByText("Нет истории")).toBeInTheDocument();
  });

  it("renders chart with enough points", () => {
    render(
      <Sparkline
        points={[
          { date: "2026-05-01", price: 100 },
          { date: "2026-05-02", price: 110 },
          { date: "2026-05-03", price: 120 },
        ]}
      />,
    );
    expect(screen.getByTestId("sparkline-chart")).toBeInTheDocument();
  });
});
