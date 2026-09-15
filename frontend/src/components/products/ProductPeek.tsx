/**
 * Product Peek — right-side drawer with product context, opened from a
 * catalog row without leaving the page (peek → page pattern).
 *
 * Shows everything the pool item already carries (image, description,
 * price, 24h change, recent-prices mini chart). Sections that need new
 * backend (full price history, cross-marketplace listings, alert rules)
 * render honest pending states — contracts are documented in
 * docs/FRONTEND_BACKEND_REQUESTS.md.
 */

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Bell, ExternalLink } from "lucide-react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  productsApi,
  type PoolProductItem,
  type PriceHistoryPeriod,
} from "@/api/products";
import { MarketplaceBadge } from "@/components/ui-custom/MarketplaceBadge";
import { PriceDisplay } from "@/components/ui-custom/PriceDisplay";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Tooltip as UiTooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useDisplayCurrency } from "@/hooks/useDisplayCurrency";
import { useMarketplaceLabelFormatter } from "@/hooks/useMarketplaceLabel";
import { CHART_PRIMARY } from "@/lib/design-tokens";
import { formatChartDate, formatPriceNumber, formatRelativeTime } from "@/lib/formatters";
import { cn } from "@/lib/utils";

export interface ProductPeekProps {
  item: PoolProductItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function formatPercent(value?: number | null): string {
  if (value == null) {
    return "—";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

const HISTORY_PERIODS: PriceHistoryPeriod[] = ["7d", "30d", "90d"];

export function ProductPeek({ item, open, onOpenChange }: ProductPeekProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const formatMarketplaceLabel = useMarketplaceLabelFormatter();
  const { apiParam: displayCurrency } = useDisplayCurrency();
  const [period, setPeriod] = useState<PriceHistoryPeriod>("30d");

  /* P2: fresh detail by id (description/brand/category grow as shops rescrape). */
  const { data: detail } = useQuery({
    queryKey: ["pool-product-detail", item?.id ?? null, displayCurrency],
    queryFn: () =>
      productsApi.getPoolProduct(item!.id, displayCurrency).then((r) => r.data),
    enabled: open && !!item,
    staleTime: 30_000,
  });

  /* P1: real per-listing price history from fact_price. */
  const { data: history } = useQuery({
    queryKey: ["pool-price-history", item?.id ?? null, period],
    queryFn: () =>
      productsApi.getPriceHistory(item!.id, period).then((r) => r.data),
    enabled: open && !!item,
    staleTime: 30_000,
  });

  const serverHistoryReady =
    history?.data_ready === true && (history?.points?.length ?? 0) >= 2;

  const historyRows = useMemo(() => {
    if (serverHistoryReady) {
      return (history?.points ?? [])
        .filter((row) => row.price != null && Number.isFinite(Number(row.price)))
        .map((row) => ({ date: row.date, price: Number(row.price) }));
    }
    /* Fallback while server history is still accumulating: the recent_prices
       already carried by the list item. */
    const rows = item?.recent_prices ?? [];
    return rows
      .filter((row) => row.price != null && Number.isFinite(Number(row.price)))
      .map((row) => ({ date: row.date, price: Number(row.price) }));
  }, [serverHistoryReady, history?.points, item?.recent_prices]);

  if (!item) {
    return null;
  }

  const view = { ...item, ...(detail ?? {}) };
  const description = detail?.description ?? item.description ?? null;
  const brand = detail?.brand ?? null;
  const category = detail?.category ?? null;

  const marketplaceLabel = formatMarketplaceLabel({
    name: view.marketplace_name,
    domain: view.marketplace_domain,
    countryCode: view.country_code,
  });
  const changeValue = view.price_change_pct ?? null;
  const hasHistory = historyRows.length >= 2;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full max-w-full overflow-y-auto border-s border-[var(--glass-border)] bg-[var(--background-surface)] p-0 sm:max-w-md"
      >
        <SheetHeader className="sr-only">
          <SheetTitle>{item.title ?? t("products.peek.title")}</SheetTitle>
        </SheetHeader>

        <div className="space-y-5 p-5">
          {/* Identity */}
          <div className="flex gap-4">
            <div className="grid size-24 shrink-0 place-items-center overflow-hidden rounded-lg border border-[var(--glass-border)] bg-[var(--background-elevated)]">
              {item.image_url ? (
                <img
                  src={item.image_url}
                  alt=""
                  className="h-full w-full object-contain"
                  loading="lazy"
                />
              ) : (
                <span className="text-2xl font-semibold text-muted-foreground">
                  {(item.title ?? "?").slice(0, 1).toUpperCase()}
                </span>
              )}
            </div>
            <div className="min-w-0 flex-1 space-y-1.5">
              <h2 className="text-base font-semibold leading-snug">
                {item.title ?? t("market.overview.untitled")}
              </h2>
              <div className="flex flex-wrap items-center gap-1.5">
                <MarketplaceBadge
                  marketplace={
                    view.marketplace_domain ||
                    view.marketplace_name ||
                    String(view.marketplace_id)
                  }
                  label={marketplaceLabel}
                  size="sm"
                />
                {brand ? (
                  <span className="label-mono rounded border border-[var(--glass-border)] px-1.5 py-0.5">
                    {brand}
                  </span>
                ) : null}
                {category ? (
                  <span className="label-mono rounded border border-[var(--glass-border)] px-1.5 py-0.5">
                    {category}
                  </span>
                ) : null}
                {view.in_stock != null && (
                  <span
                    className={cn(
                      "label-mono",
                      item.in_stock
                        ? "!text-[var(--status-ok)]"
                        : "!text-[var(--status-error)]",
                    )}
                  >
                    {view.in_stock
                      ? t("products.peek.inStock")
                      : t("products.peek.outOfStock")}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Price block */}
          <div className="surface-sunken flex items-end justify-between gap-3 rounded-lg p-3">
            <div>
              <p className="label-mono">{t("products.price")}</p>
              <PriceDisplay
                className="mt-0.5 text-xl font-semibold"
                localAmount={item.price}
                localCurrency={item.currency}
                displayAmount={item.display_price}
                displayCurrency={item.display_currency}
                conversionAvailable={item.conversion_available}
              />
            </div>
            <div className="text-right">
              <p className="label-mono">{t("products.change24h")}</p>
              <p
                className={cn(
                  "mt-0.5 font-mono text-sm font-medium tabular-nums",
                  changeValue != null && changeValue > 0 && "text-[var(--color-price-up)]",
                  changeValue != null && changeValue < 0 && "text-[var(--color-price-down)]",
                )}
              >
                {formatPercent(changeValue)}
              </p>
            </div>
          </div>

          {/* Description */}
          {description ? (
            <div>
              <p className="label-mono mb-1.5">{t("products.peek.description")}</p>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {description}
              </p>
            </div>
          ) : null}

          {/* Price history — server fact_price series (P1), recent_prices fallback */}
          <div>
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <p className="label-mono">{t("products.peek.priceHistory")}</p>
              <div className="flex gap-0.5 rounded-md border border-[var(--glass-border)] p-0.5">
                {HISTORY_PERIODS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setPeriod(option)}
                    className={cn(
                      "rounded px-2 py-0.5 text-2xs transition-colors",
                      period === option
                        ? "bg-[var(--accent-bg-subtle)] font-medium text-[var(--foreground)]"
                        : "text-muted-foreground hover:text-[var(--foreground)]",
                    )}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
            {hasHistory ? (
              <div className="h-[140px] w-full">
                <ResponsiveContainer width="100%" height={140}>
                  <AreaChart data={historyRows} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10 }}
                      tickLine={false}
                      axisLine={false}
                      minTickGap={32}
                      tickFormatter={(value: string) => formatChartDate(value, locale)}
                    />
                    <YAxis
                      tick={{ fontSize: 10 }}
                      tickLine={false}
                      axisLine={false}
                      width={46}
                      domain={["auto", "auto"]}
                      tickFormatter={(value: number) => formatPriceNumber(value, locale)}
                    />
                    <Tooltip
                      formatter={(value: number) => [
                        `${formatPriceNumber(value, locale)} ${
                          serverHistoryReady ? history?.currency ?? view.currency : view.currency
                        }`,
                        "",
                      ]}
                      labelFormatter={(value: string) => formatChartDate(value, locale)}
                    />
                    <Area
                      type="monotone"
                      dataKey="price"
                      stroke={CHART_PRIMARY}
                      fill={CHART_PRIMARY}
                      fillOpacity={0.12}
                      strokeWidth={1.8}
                      dot={false}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {t("products.peek.historyEmpty")}
              </p>
            )}
          </div>

          {/* Cross-marketplace listings — backend pending */}
          <div>
            <p className="label-mono mb-1.5">{t("products.peek.listings")}</p>
            <p className="text-sm text-muted-foreground">
              {t("products.peek.listingsPending")}
            </p>
          </div>

          {/* Meta */}
          {item.last_checked_at ? (
            <p className="text-xs text-muted-foreground">
              {t("products.peek.lastChecked")}:{" "}
              {formatRelativeTime(item.last_checked_at, locale)}
            </p>
          ) : null}

          {/* Actions */}
          <div className="flex flex-wrap items-center gap-2 border-t border-[var(--glass-border)] pt-4">
            <UiTooltip>
              <TooltipTrigger asChild>
                <span>
                  <Button variant="outline" size="sm" disabled>
                    <Bell className="me-1.5 size-3.5" />
                    {t("products.peek.setAlert")}
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent side="top" className="surface-overlay">
                {t("products.peek.alertPending")}
              </TooltipContent>
            </UiTooltip>
            {item.url ? (
              <Button variant="outline" size="sm" asChild>
                <a href={item.url} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="me-1.5 size-3.5" />
                  {t("products.peek.openExternal")}
                </a>
              </Button>
            ) : null}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
