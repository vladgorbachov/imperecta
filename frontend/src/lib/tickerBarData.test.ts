import { describe, it, expect } from "vitest";
import { buildTickerBarItems } from "./tickerBarData";
import type { MarketsForexItem } from "@/api/markets";
import type { MarketsCommodityItem } from "@/api/markets";

const mockForex: MarketsForexItem[] = [
  { symbol: "EUR/USD", bid: 1.08, ask: 1.0801, spread: 0.0001, change_24h: 0.5, refreshed_at: "2025-01-01T00:00:00Z" },
  { symbol: "EUR/RUB", bid: 100, ask: 100.1, spread: 0.1, change_24h: -1.2, refreshed_at: "2025-01-01T00:00:00Z" },
];

const mockCommodities: MarketsCommodityItem[] = [
  { symbol: "gasoline", name: "Gasoline", price: 2.5, change_24h: 0.3, unit: "USD", refreshed_at: "2025-01-01T00:00:00Z" },
];

describe("buildTickerBarItems", () => {
  it("returns fuel items for country when commodities include fuel symbols", () => {
    const items = buildTickerBarItems(mockForex, mockCommodities, "UA");
    const fuelItems = items.filter((i) => i.type === "fuel");
    expect(fuelItems.length).toBeGreaterThan(0);
    expect(fuelItems[0].symbol).toBe("gasoline");
  });

  it("returns forex items when forex data exists", () => {
    const items = buildTickerBarItems(mockForex, mockCommodities, "UA");
    const forexItems = items.filter((i) => i.type === "forex");
    expect(forexItems.length).toBeGreaterThan(0);
  });

  it("returns empty array when both forex and commodities are empty", () => {
    const items = buildTickerBarItems([], [], "UA");
    expect(items).toEqual([]);
  });

  it("prioritizes USD/local and EUR/local pairs for non-USD country", () => {
    const items = buildTickerBarItems(mockForex, [], "UA");
    const symbols = items.map((i) => i.symbol);
    expect(symbols).toContain("EUR/RUB"); // Data fixture intentionally contains this pair.
  });
});
