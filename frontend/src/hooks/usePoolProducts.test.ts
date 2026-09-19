import { describe, expect, it } from "vitest";
import type { PoolProductItem, PoolProductsResponse } from "@/api/products";
import { mergeRefreshedItems } from "./usePoolProducts";

function item(id: string, price: number, extra: Partial<PoolProductItem> = {}): PoolProductItem {
  return {
    id,
    marketplace_id: "m",
    url: `https://shop.example/${id}`,
    currency: "EUR",
    status: "ok",
    price,
    recent_prices: [{ date: "2026-09-18", price, currency: "EUR" }],
    ...extra,
  };
}

describe("mergeRefreshedItems", () => {
  const page: PoolProductsResponse = {
    items: [item("a", 10), item("b", 20)],
    total: 2,
    limit: 20,
    offset: 0,
  };

  it("swaps in refreshed rows by id and keeps page order", () => {
    const merged = mergeRefreshedItems(page, [item("b", 25, { recent_prices: [] })]);
    expect(merged.items.map((i) => i.id)).toEqual(["a", "b"]);
    expect(merged.items[1].price).toBe(25);
    // the refresh returned no sparkline: the snapshot's stays
    expect(merged.items[1].recent_prices).toHaveLength(1);
    expect(merged.items[0]).toBe(page.items[0]);
  });

  it("returns the same page object when nothing on screen changed", () => {
    expect(mergeRefreshedItems(page, [])).toBe(page);
    expect(mergeRefreshedItems(page, [item("zzz", 1)])).toBe(page);
  });
});
