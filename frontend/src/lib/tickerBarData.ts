/**
 * Build ticker bar display items from forex + commodities.
 * Prioritizes: fuel (gasoline, diesel, LPG) for active country, then FX pairs.
 */

import type { MarketsForexItem } from "@/api/markets";
import type { MarketsCommodityItem } from "@/api/markets";
import { getCurrencyForCountry } from "./countries";

export interface TickerBarItem {
  symbol: string;
  name: string;
  price: number;
  change_24h: number | null;
  currency: string | null;
  type: "fuel" | "forex";
}

/** Fuel symbols (case-insensitive). */
const FUEL_SYMBOLS = new Set(
  ["gasoline", "diesel", "gas", "lpg", "petrol"].map((s) => s.toLowerCase())
);

function isFuelSymbol(symbol: string): boolean {
  return FUEL_SYMBOLS.has(symbol.toLowerCase());
}

/** High-rank cross pairs (when local not in pair). */
const CROSS_PAIRS = new Set([
  "USD/EUR",
  "EUR/USD",
  "GBP/USD",
  "USD/GBP",
  "USD/JPY",
  "JPY/USD",
  "USD/CNY",
  "CNY/USD",
  "EUR/GBP",
  "GBP/EUR",
]);

function normalizePair(s: string): string {
  return s.replace(/\s/g, "").toUpperCase();
}

export function buildTickerBarItems(
  forexItems: MarketsForexItem[],
  commodityItems: MarketsCommodityItem[],
  countryCode: string
): TickerBarItem[] {
  const local = getCurrencyForCountry(countryCode);
  const result: TickerBarItem[] = [];

  // 1. Fuel: gasoline, diesel, gas/LPG from commodities
  const fuelItems = commodityItems.filter((c) =>
    isFuelSymbol(c.symbol)
  );
  for (const c of fuelItems) {
    result.push({
      symbol: c.symbol,
      name: c.name ?? c.symbol,
      price: c.price,
      change_24h: c.change_24h,
      currency: c.unit ?? null,
      type: "fuel",
    });
  }

  // 2. FX: prioritize USD/local, EUR/local, GBP/local, then cross pairs
  const forexBySymbol = new Map(
    forexItems.map((f) => [normalizePair(f.symbol), f])
  );

  const priorityPairs: string[] = [];
  if (local !== "USD") priorityPairs.push(`USD/${local}`, `${local}/USD`);
  if (local !== "EUR") priorityPairs.push(`EUR/${local}`, `${local}/EUR`);
  if (local !== "GBP") priorityPairs.push(`GBP/${local}`, `${local}/GBP`);

  for (const pair of priorityPairs) {
    const normalized = normalizePair(pair);
    const f = forexBySymbol.get(normalized);
    if (f) {
      result.push({
        symbol: f.symbol,
        name: f.symbol,
        price: f.bid,
        change_24h: f.change_24h,
        currency: "USD",
        type: "forex",
      });
      forexBySymbol.delete(normalized);
    }
  }

  for (const pair of CROSS_PAIRS) {
    const f = forexBySymbol.get(normalizePair(pair));
    if (f) {
      result.push({
        symbol: f.symbol,
        name: f.symbol,
        price: f.bid,
        change_24h: f.change_24h,
        currency: "USD",
        type: "forex",
      });
      forexBySymbol.delete(normalizePair(pair));
    }
  }

  // 3. Remaining forex
  for (const f of forexBySymbol.values()) {
    result.push({
      symbol: f.symbol,
      name: f.symbol,
      price: f.bid,
      change_24h: f.change_24h,
      currency: "USD",
      type: "forex",
    });
  }

  return result;
}
