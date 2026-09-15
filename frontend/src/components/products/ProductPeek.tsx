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

import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Bell, ExternalLink } from "lucide-react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PoolProductItem } from "@/api/products";
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

export function ProductPeek({ item, open, onOpenChange }: ProductPeekProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const formatMarketplaceLabel = useMarketplaceLabelFormatter();

  const historyRows = useMemo(() => {
    const rows = item?.recent_prices ?? [];
    return rows
      .filter((row) => row.price != null && Number.isFinite(Number(row.price)))
      .map((row) => ({ date: row.date, price: Number(row.price) }));
  }, [item?.recent_prices]);

  if (!item) {
    return null;
  }

  const marketplaceLabel = formatMarketplaceLabel({
    name: item.marketplace_name,
    domain: item.marketplace_domain,
    countryCode: item.country_code,
  });
  const changeValue = item.price_change_pct ?? null;
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
                    item.marketplace_domain ||
                    item.marketplace_name ||
                    String(item.marketplace_id)
                  }
                  label={marketplaceLabel}
                  size="sm"
                />
                {item.in_stock != null && (
                  <span
                    className={cn(
                      "label-mono",
                      item.in_stock
                        ? "!text-[var(--status-ok)]"
                        : "!text-[var(--status-error)]",
                    )}
                  >
                    {item.in_stock
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
          {item.description ? (
            <div>
              <p className="label-mono mb-1.5">{t("products.peek.description")}</p>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {item.description}
              </p>
            </div>
          ) : null}

          {/* Recent price history (from pool payload; full history endpoint pending) */}
          <div>
            <p className="label-mono mb-1.5">{t("products.peek.priceHistory")}</p>
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
                        `${formatPriceNumber(value, locale)} ${item.currency}`,
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
