/**
 * Market Pulse — the live corner of the Overview dashboard.
 * Two real-data sections, no synthetic content:
 *  - Top marketplaces by pool size (animated bars, /pool/marketplace-stats).
 *  - Latest price moves (auto-scrolling stream when there are enough rows,
 *    /markets/movements sorted by changed_at; honest empty while history
 *    accumulates). Animations honor prefers-reduced-motion via the global
 *    reduced-motion kill-switch in index.css.
 */

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { TrendingDown, TrendingUp } from "lucide-react";
import {
  marketsApi,
  marketsQueryKeys,
  type MoverItem,
  type MovementsQueryParams,
} from "@/api/markets";
import { formatRelativeTime } from "@/lib/formatters";
import { safeNumber } from "@/lib/safeNumber";
import { cn } from "@/lib/utils";

const TOP_MARKETPLACES = 6;
const STREAM_LIMIT = 14;
/** Auto-scroll only when the list is long enough to loop believably. */
const STREAM_MIN_FOR_LOOP = 6;

function PulseRow({ item, locale }: { item: MoverItem; locale: string }) {
  const change = safeNumber(item.price_change_pct);
  const isUp = item.direction === "up";
  return (
    <li className="flex items-center gap-2.5 py-1.5">
      <span
        className={cn(
          "grid size-5 shrink-0 place-items-center rounded",
          isUp
            ? "bg-[var(--color-price-up-bg)] text-[var(--color-price-up)]"
            : "bg-[var(--color-price-down-bg)] text-[var(--color-price-down)]",
        )}
        aria-hidden
      >
        {isUp ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm leading-tight">{item.product_name}</p>
        <p className="truncate text-2xs text-muted-foreground">
          {item.marketplace_name} · {formatRelativeTime(item.changed_at, locale)}
        </p>
      </div>
      <span
        className={cn(
          "shrink-0 font-mono text-xs font-medium tabular-nums",
          isUp ? "text-[var(--color-price-up)]" : "text-[var(--color-price-down)]",
        )}
      >
        {change > 0 ? "+" : ""}
        {change.toFixed(1)}%
      </span>
    </li>
  );
}

export function MarketPulseWidget({ countryCode }: { countryCode: string | null }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const [barsIn, setBarsIn] = useState(false);

  const { data: mpStats } = useQuery({
    queryKey: marketsQueryKeys.poolMarketplaceStats(),
    queryFn: () => marketsApi.getPoolMarketplaceStats().then((r) => r.data),
    staleTime: 60_000,
    refetchInterval: 120_000,
  });

  const moversParams = useMemo(
    (): MovementsQueryParams => ({
      period: "24h",
      direction: "all",
      sort_by: "changed_at",
      limit: STREAM_LIMIT,
      offset: 0,
      country_code: countryCode ?? undefined,
    }),
    [countryCode],
  );
  const { data: movers } = useQuery({
    queryKey: marketsQueryKeys.movements(moversParams),
    queryFn: () => marketsApi.getMovers(moversParams).then((r) => r.data),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  const topMarketplaces = useMemo(() => {
    const rows = [...(mpStats ?? [])]
      .filter((row) => row.product_count > 0)
      .sort((a, b) => b.product_count - a.product_count)
      .slice(0, TOP_MARKETPLACES);
    const max = rows[0]?.product_count ?? 1;
    return rows.map((row) => ({
      label: row.marketplace_name ?? row.marketplace_domain,
      count: row.product_count,
      share: Math.max(4, Math.round((row.product_count / max) * 100)),
    }));
  }, [mpStats]);

  /* Bars grow from 0 on mount (CSS width transition). */
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setBarsIn(true));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const moves = movers?.items ?? [];
  const loop = moves.length >= STREAM_MIN_FOR_LOOP;

  return (
    <div
      className="surface-base flex h-full min-w-0 flex-col rounded-xl p-3.5"
      data-testid="market-pulse-widget"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="label-mono !text-[var(--foreground)]">
          {t("dashboard.pulse.title")}
        </h3>
        <span className="label-mono inline-flex items-center gap-1.5 !text-[var(--status-ok)]">
          <span className="relative flex size-1.5" aria-hidden>
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--status-ok)] opacity-60" />
            <span className="relative inline-flex size-1.5 rounded-full bg-[var(--status-ok)]" />
          </span>
          {t("dashboard.pulse.live")}
        </span>
      </div>

      {/* Top marketplaces — animated bars */}
      <p className="label-mono mb-2">{t("dashboard.pulse.topMarketplaces")}</p>
      <div className="space-y-1.5">
        {topMarketplaces.map((row) => (
          <div key={row.label} className="flex items-center gap-2">
            <span className="w-24 shrink-0 truncate text-xs">{row.label}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--surface-sunken-bg)]">
              <div
                className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-700 ease-out"
                style={{ width: barsIn ? `${row.share}%` : "0%" }}
              />
            </div>
            <span className="w-14 shrink-0 text-right font-mono text-2xs tabular-nums text-muted-foreground">
              {row.count.toLocaleString(locale)}
            </span>
          </div>
        ))}
      </div>

      {/* Latest price moves — auto-scrolling stream */}
      <p className="label-mono mb-1 mt-4">{t("dashboard.pulse.movements")}</p>
      {moves.length === 0 ? (
        <p className="py-3 text-sm text-muted-foreground">
          {t("movements.emptyHint")}
        </p>
      ) : (
        <div
          className="relative min-h-0 flex-1 overflow-hidden"
          style={{ maskImage: "linear-gradient(#000 82%, transparent)" }}
        >
          <ul className={cn(loop && "pulse-stream")}>
            {moves.map((item) => (
              <PulseRow
                key={`${item.product_name}-${item.changed_at}`}
                item={item}
                locale={locale}
              />
            ))}
            {/* Second copy makes the loop seamless (translateY(-50%)). */}
            {loop
              ? moves.map((item) => (
                  <PulseRow
                    key={`dup-${item.product_name}-${item.changed_at}`}
                    item={item}
                    locale={locale}
                  />
                ))
              : null}
          </ul>
        </div>
      )}
    </div>
  );
}
