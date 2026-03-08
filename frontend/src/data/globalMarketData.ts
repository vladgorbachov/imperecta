/**
 * Global market data for dashboard ticker when user has no products.
 * Seeded random for consistent but varied data (simulates live market).
 */

export interface MarketDataItem {
  id: string;
  marketplace: string;
  marketplace_domain: string;
  product_name: string;
  price: number;
  currency: string;
  change_24h: number;
  change_3d: number;
  change_1w: number;
  change_1m: number;
  sparkline_data: number[];
  last_updated: string;
}

const seededRandom = (seed: number): number => {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
};

export function generateGlobalMarketData(): MarketDataItem[] {
  const now = Date.now();
  const items: Array<{ mp: string; domain: string; product: string; base: number; cur: string }> = [
    { mp: "Wildberries", domain: "wildberries.ru", product: "iPhone 16 Pro Max 256GB", base: 129990, cur: "RUB" },
    { mp: "Ozon", domain: "ozon.ru", product: "Samsung Galaxy S25 Ultra", base: 109990, cur: "RUB" },
    { mp: "Wildberries", domain: "wildberries.ru", product: "Sony WH-1000XM5", base: 24990, cur: "RUB" },
    { mp: "Ozon", domain: "ozon.ru", product: "MacBook Air M4 15\"", base: 159990, cur: "RUB" },
    { mp: "Lamoda", domain: "lamoda.ru", product: "Nike Air Max 90", base: 12990, cur: "RUB" },
    { mp: "Avito", domain: "avito.ru", product: "PlayStation 5 Pro", base: 59990, cur: "RUB" },
    { mp: "SberMegaMarket", domain: "sbermegamarket.ru", product: "Dyson V15 Detect", base: 49990, cur: "RUB" },
    { mp: "Kaspi.kz", domain: "kaspi.kz", product: "Xiaomi 14 Ultra", base: 349900, cur: "KZT" },
    { mp: "Kaspi.kz", domain: "kaspi.kz", product: "iPad Pro 13\" M4", base: 499900, cur: "KZT" },
    { mp: "Wildberries KZ", domain: "wildberries.kz", product: "AirPods Pro 3", base: 129900, cur: "KZT" },
    { mp: "Rozetka", domain: "rozetka.ua", product: "Samsung QN90D 55\"", base: 45999, cur: "UAH" },
    { mp: "Rozetka", domain: "rozetka.ua", product: "Google Pixel 9 Pro", base: 37999, cur: "UAH" },
    { mp: "Prom.ua", domain: "prom.ua", product: "Bose QC Ultra", base: 14999, cur: "UAH" },
    { mp: "Hotline", domain: "hotline.ua", product: "LG OLED C4 65\"", base: 62999, cur: "UAH" },
    { mp: "Amazon DE", domain: "amazon.de", product: "Canon EOS R6 III", base: 2499, cur: "EUR" },
    { mp: "Amazon DE", domain: "amazon.de", product: "DJI Mini 4 Pro", base: 799, cur: "EUR" },
    { mp: "MediaMarkt", domain: "mediamarkt.de", product: "Apple Watch Ultra 3", base: 899, cur: "EUR" },
    { mp: "Zalando", domain: "zalando.com", product: "Adidas Ultraboost 24", base: 189, cur: "EUR" },
    { mp: "Otto", domain: "otto.de", product: "Herman Miller Aeron", base: 1399, cur: "EUR" },
    { mp: "Allegro", domain: "allegro.pl", product: "OnePlus 13", base: 3999, cur: "PLN" },
    { mp: "Allegro", domain: "allegro.pl", product: "JBL Charge 5", base: 449, cur: "PLN" },
    { mp: "Ceneo", domain: "ceneo.pl", product: "Roborock S8 MaxV", base: 3299, cur: "PLN" },
    { mp: "eMAG RO", domain: "emag.ro", product: "Garmin Fenix 8", base: 3499, cur: "RON" },
    { mp: "Trendyol", domain: "trendyol.com", product: "Xbox Series X", base: 14999, cur: "TRY" },
    { mp: "Cdiscount", domain: "cdiscount.com", product: "Nespresso Vertuo", base: 179, cur: "EUR" },
    { mp: "Fnac", domain: "fnac.com", product: "Lego Technic Ferrari", base: 399, cur: "EUR" },
    { mp: "Bol.com", domain: "bol.com", product: "Philips Hue Starter Kit", base: 129, cur: "EUR" },
    { mp: "Kufar", domain: "kufar.by", product: "Logitech MX Master 3S", base: 289, cur: "BYN" },
    { mp: "999.md", domain: "999.md", product: "Instant Pot Pro Plus", base: 2499, cur: "MDL" },
    { mp: "Zoommer", domain: "zoommer.ge", product: "Nintendo Switch 2", base: 1299, cur: "GEL" },
    { mp: "List.am", domain: "list.am", product: "Apple Watch Ultra 3", base: 459000, cur: "AMD" },
    { mp: "Uzum", domain: "uzum.uz", product: "Samsung Galaxy S25", base: 11990000, cur: "UZS" },
    { mp: "eMAG BG", domain: "emag.bg", product: "Xiaomi Robot Vacuum", base: 699, cur: "BGN" },
    { mp: "220.lv", domain: "220.lv", product: "Sony PS5 DualSense", base: 69, cur: "EUR" },
    { mp: "Pigu.lt", domain: "pigu.lt", product: "Kindle Paperwhite", base: 149, cur: "EUR" },
  ];

  return items.map((item, i) => {
    const seed = now / 600000 + i;
    const volatility = seededRandom(seed * 7) * 0.15;
    const direction = seededRandom(seed * 13) > 0.5 ? 1 : -1;

    const change24h = +(direction * volatility * 100 * seededRandom(seed)).toFixed(2);
    const change3d = +(change24h * (1 + seededRandom(seed * 2) * 2)).toFixed(2);
    const change1w = +(change3d * (1 + seededRandom(seed * 3))).toFixed(2);
    const change1m = +(change1w * (1 + seededRandom(seed * 4) * 0.5)).toFixed(2);

    const sparkline = Array.from({ length: 30 }, (_, j) => {
      const s = seededRandom(i * 100 + j + Math.floor(now / 86400000));
      return item.base * (0.9 + s * 0.2);
    });

    return {
      id: String(i + 1),
      marketplace: item.mp,
      marketplace_domain: item.domain,
      product_name: item.product,
      price: Math.round(item.base * (1 + change24h / 100)),
      currency: item.cur,
      change_24h: change24h,
      change_3d: change3d,
      change_1w: change1w,
      change_1m: change1m,
      sparkline_data: sparkline,
      last_updated: new Date(now - Math.floor(seededRandom(seed * 99) * 3600000)).toISOString(),
    };
  });
}

export function sortMarketData(
  data: MarketDataItem[],
  tab: string
): MarketDataItem[] {
  const sorted = [...data];
  switch (tab) {
    case "volatile":
      return sorted.sort(
        (a, b) =>
          Math.max(Math.abs(b.change_24h), Math.abs(b.change_3d)) -
          Math.max(Math.abs(a.change_24h), Math.abs(a.change_3d))
      );
    case "trending":
      return sorted.sort((a, b) => Math.abs(b.change_24h) - Math.abs(a.change_24h));
    case "gainers":
      return sorted.filter((i) => i.change_24h > 0).sort((a, b) => b.change_24h - a.change_24h);
    case "losers":
      return sorted.filter((i) => i.change_24h < 0).sort((a, b) => a.change_24h - b.change_24h);
    case "recent":
      return sorted.sort(
        (a, b) =>
          new Date(b.last_updated).getTime() - new Date(a.last_updated).getTime()
      );
    default:
      return sorted;
  }
}
