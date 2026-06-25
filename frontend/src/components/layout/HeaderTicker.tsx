/**
 * Read-only marquee ticker for the global Header.
 *
 * Reuses GET /api/markets/ticker.
 * Integer-pixel loop distance (measured on mount / items change only); 30s fixed duration.
 * Fully transparent: no card chrome, no background, no border, no radius.
 */

import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { marketsApi, marketsQueryKeys } from "@/api/markets";
import { safeFixed, safeNumber } from "@/lib/safeNumber";
import { cn } from "@/lib/utils";

const STALE_2H = 2 * 60 * 60 * 1000;

type TickerItemData = {
  symbol: string;
  name: string | null;
  price: number;
  change_24h: number | null;
  currency: string | null;
};

function tickerItemsSignature(items: TickerItemData[]): string {
  return items
    .map(
      (item) =>
        `${item.symbol}:${item.price}:${item.change_24h ?? ""}:${item.name ?? ""}:${item.currency ?? ""}`,
    )
    .join("|");
}

export function formatTickerValue(item: TickerItemData, locale: string): string {
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

export function TickerItem({ item, locale }: { item: TickerItemData; locale: string }) {
  const ch = item.change_24h ?? 0;
  const isZero = ch === 0;
  const isPositive = ch > 0;
  const label = item.name ?? item.symbol ?? "";
  const value = formatTickerValue(item, locale);

  return (
    <span className="inline-flex shrink-0 items-center gap-2">
      <span className="text-xs font-medium">{label}</span>
      <span className="font-mono text-sm tabular-nums">{value}</span>
      {item.change_24h != null && (
        <span
          className={cn(
            "text-xs font-mono tabular-nums",
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
  const itemsSignature = useMemo(() => tickerItemsSignature(items), [items]);
  const doubled = useMemo(() => [...items, ...items], [itemsSignature]);

  const trackRef = useRef<HTMLDivElement>(null);
  const [copyWidthPx, setCopyWidthPx] = useState(0);

  useLayoutEffect(() => {
    const track = trackRef.current;
    if (!track || items.length === 0) {
      setCopyWidthPx(0);
      return;
    }
    setCopyWidthPx(Math.round(track.scrollWidth / 2));
  }, [itemsSignature, items.length]);

  const hasItems = items.length > 0;
  const trackStyle = useMemo((): CSSProperties & { "--marquee-distance"?: string } => {
    return {
      "--marquee-distance": copyWidthPx > 0 ? `${copyWidthPx}px` : "50%",
    };
  }, [copyWidthPx]);

  return (
    <div
      className={cn(
        "group min-w-0 overflow-hidden",
        !hasItems && "h-0 pointer-events-none",
        className,
      )}
      style={{
        maskImage: hasItems
          ? "linear-gradient(to right, transparent 0, #000 6%, #000 94%, transparent 100%)"
          : undefined,
        WebkitMaskImage: hasItems
          ? "linear-gradient(to right, transparent 0, #000 6%, #000 94%, transparent 100%)"
          : undefined,
      }}
      aria-hidden={!hasItems}
    >
      <div
        key="marquee-track"
        ref={trackRef}
        className={cn(
          "flex animate-marquee whitespace-nowrap group-hover:[animation-play-state:paused]",
          !hasItems && "invisible",
        )}
        style={trackStyle}
      >
        {doubled.map((item, index) => (
          <span key={`${item.symbol}-${index}`} className="flex shrink-0 items-center pe-7">
            <TickerItem item={item} locale={locale} />
          </span>
        ))}
      </div>
    </div>
  );
}
