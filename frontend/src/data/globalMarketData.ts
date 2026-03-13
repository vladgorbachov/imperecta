/**
 * Fallback market overview data when API returns empty.
 * Used to ensure Market Overview table always shows data for demo/empty state.
 */

import type { MarketsOverviewItem } from "@/api/markets";

const SAMPLE_PRODUCTS = [
  { name: "Wireless Earbuds Pro", marketplace: "ozon", domain: "ozon.ru" },
  { name: "Smart Watch Series 5", marketplace: "wildberries", domain: "wildberries.ru" },
  { name: "Portable Power Bank 20000mAh", marketplace: "kaspi", domain: "kaspi.kz" },
  { name: "Mechanical Keyboard RGB", marketplace: "ozon", domain: "ozon.ru" },
  { name: "USB-C Hub 7-in-1", marketplace: "wildberries", domain: "wildberries.ru" },
  { name: "Bluetooth Speaker", marketplace: "ozon", domain: "ozon.ru" },
  { name: "Wireless Mouse", marketplace: "kaspi", domain: "kaspi.kz" },
  { name: "HD Webcam 1080p", marketplace: "wildberries", domain: "wildberries.ru" },
  { name: "SSD 1TB NVMe", marketplace: "ozon", domain: "ozon.ru" },
  { name: "Monitor Arm Mount", marketplace: "kaspi", domain: "kaspi.kz" },
];

function generateSparkline(base: number, variance: number): number[] {
  const points: number[] = [];
  let v = base;
  for (let i = 0; i < 15; i++) {
    v += (Math.random() - 0.5) * variance;
    points.push(Math.max(base * 0.7, Math.min(base * 1.3, v)));
  }
  return points;
}

export function generateGlobalMarketData(): MarketsOverviewItem[] {
  const now = new Date().toISOString();
  return SAMPLE_PRODUCTS.map((p, i) => {
    const price = 1500 + Math.random() * 15000;
    const ch24 = (Math.random() - 0.5) * 20;
    const ch3d = ch24 + (Math.random() - 0.5) * 5;
    const ch1w = ch3d + (Math.random() - 0.5) * 8;
    const ch1m = ch1w + (Math.random() - 0.5) * 10;
    return {
      id: `fallback-${i}-${Date.now()}`,
      marketplace: p.marketplace,
      marketplace_domain: p.domain,
      product_name: p.name,
      price: Math.round(price * 100) / 100,
      currency: "RUB",
      change_24h: Math.round(ch24 * 10) / 10,
      change_3d: Math.round(ch3d * 10) / 10,
      change_1w: Math.round(ch1w * 10) / 10,
      change_1m: Math.round(ch1m * 10) / 10,
      sparkline_data: generateSparkline(price, price * 0.05),
      last_updated: now,
    };
  });
}
