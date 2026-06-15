/**
 * Read-only marquee ticker for the global Header.
 *
 * Reuses GET /api/markets/ticker.
 * Renders nothing when there are no items (no skeleton, no placeholder).
 * Fully transparent: no card chrome, no background, no border, no radius.
 */

import { useTranslation } from "react-i18next";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { marketsApi, marketsQueryKeys } from "@/api/markets";
import { safeFixed, safeNumber } from "@/lib/safeNumber";
import { cn } from "@/lib/utils";

const STALE_2H = 2 * 60 * 60 * 1000;

export function formatTickerValue(
  item: {
    symbol: string;
    name: string | null;
    price: number;
    change_24h: number | null;
    currency: string | null;
  },
  locale: string,
): string {
  const sym = item.symbol ?? "";
  const isForex = sym.includes("/");
  const isFuel = /gasoline|diesel|lpg|petrol|fuel/i.test(sym);

  if (isForex) {
    const quote = sym.split("/")[1] ?? "";
    const decimals = ["USD", "GBP", "CHF", "JPY"].includes(quote) ? 4 : 2;
    return safeFixed(item.price, decimals);
  }
  if (isFuel) {
    const cur = item.currency ?? "";
    return `${safeFixed(item.price, 1)} ${cur}/L`;
  }
  const normalizedCurrency = (item.currency ?? "").trim().toUpperCase();
  if (!normalizedCurrency) {
    return safeFixed(item.price, 2);
  }
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: normalizedCurrency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(safeNumber(item.price));
  } catch {
    return `${safeFixed(item.price, 0)} ${normalizedCurrency}`;
  }
}

export function TickerItem({
  item,
  locale,
}: {
  item: {
    symbol: string;
    name: string | null;
    price: number;
    change_24h: number | null;
    currency: string | null;
  };
  locale: string;
}) {
  const ch = item.change_24h ?? 0;
  const isZero = ch === 0;
  const isPositive = ch > 0;
  const label = item.name ?? item.symbol ?? "";
  const value = formatTickerValue(item, locale);

  return (
    <span className="inline-flex shrink-0 items-center gap-2">
      <span className="text-xs font-medium">{label}</span>
      <span className="font-mono text-sm">{value}</span>
      {item.change_24h != null && (
        <span
          className={cn(
            "text-xs font-mono",
            isZero
              ? "text-muted-foreground"
              : isPositive
                ? "text-[var(--color-price-down)]"
                : "text-[var(--color-price-up)]",
          )}
        >
          {isPositive ? "+" : ""}
          {safeFixed(ch, 1)}%
        </span>
      )}
    </span>
  );
}

interface HeaderTickerProps {
  className?: string;
}

export function HeaderTicker({ className }: HeaderTickerProps) {
  const { i18n } = useTranslation();
  const locale = i18n.language || "en";

  const { data: tickerData } = useQuery({
    queryKey: marketsQueryKeys.ticker(),
    queryFn: () => marketsApi.getTicker().then((r) => r.data),
    staleTime: STALE_2H,
    refetchInterval: STALE_2H,
    placeholderData: keepPreviousData,
  });

  const items = tickerData?.items ?? [];
  if (items.length === 0) {
    return null;
  }

  return (
    <div className={cn("group min-w-0 overflow-hidden", className)}>
      <div className="flex animate-marquee gap-7 whitespace-nowrap group-hover:[animation-play-state:paused]">
        {[...items, ...items].map((item, i) => (
          <span key={`${item.symbol}-${i}`} className="flex shrink-0 items-center gap-2">
            <TickerItem item={item} locale={locale} />
            <span
              className="shrink-0 text-[var(--foreground-subtle)]"
              style={{ width: 40 }}
            >
              |
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
