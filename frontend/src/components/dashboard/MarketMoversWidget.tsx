/**
 * Price movements list for the dashboard overview (24h window).
 *
 * List shape: one getMovers call, grouped into gainers/losers on the client.
 * SWAP: for guaranteed 5+5, replace with two calls — direction=up limit=5
 * and direction=down limit=5 — at this seam only.
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  marketsApi,
  marketsQueryKeys,
  type MoverItem,
  type MovementsQueryParams,
} from "@/api/markets";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { MarketplaceBadge } from "@/components/ui-custom/MarketplaceBadge";
import { PriceDisplay } from "@/components/ui-custom/PriceDisplay";
import { TrendBadge } from "@/components/ui-custom/TrendBadge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { DisplayCurrency } from "@/lib/displayCurrency";
import type { ConvertiblePriceFields } from "@/lib/displayCurrency";
import { cn } from "@/lib/utils";

const MOVERS_LIST_BASE: MovementsQueryParams = {
  period: "24h",
  sort_by: "abs_change",
  threshold: 0,
  direction: "all",
  limit: 10,
  offset: 0,
};

function parseApiDecimal(value: number | string | null | undefined): number | null {
  if (value == null || value === "") {
    return null;
  }
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function moverPriceFields(
  nativeAmount: number | string | null | undefined,
  item: MoverItem,
  role: "old" | "new",
): ConvertiblePriceFields {
  const displayAmount = role === "old" ? item.display_old_price : item.display_new_price;
  return {
    localAmount: parseApiDecimal(nativeAmount),
    localCurrency: item.currency,
    displayAmount: parseApiDecimal(displayAmount ?? null),
    displayCurrency: item.display_currency ?? null,
    conversionAvailable: item.conversion_available ?? false,
  };
}

function MoverRow({ item }: { item: MoverItem }) {
  const { t } = useTranslation();
  const pct = parseApiDecimal(item.price_change_pct) ?? 0;
  const hasOldPrice = item.old_price != null;

  return (
    <li
      className={cn(
        "flex flex-col gap-2 border-b border-border/60 py-2.5 last:border-b-0",
        "sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-x-3 sm:gap-y-1",
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <MarketplaceBadge
          marketplace={item.marketplace_domain ?? item.marketplace_name}
          label={item.marketplace_name}
          size="sm"
          className="shrink-0"
        />
        <span
          className="min-w-0 truncate text-sm font-medium"
          title={item.product_name}
        >
          {item.product_name}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2 sm:justify-end">
        <div className="flex flex-wrap items-center gap-1.5 text-sm">
          {hasOldPrice ? (
            <>
              {item.old_price_reconstructed && (
                <TooltipProvider delayDuration={200}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span
                        className="text-xs text-muted-foreground"
                        aria-label={t("market.overview.movements.reconstructed")}
                      >
                        ≈
                      </span>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-xs text-xs">
                      {t("market.overview.movements.reconstructed")}
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
              <PriceDisplay
                {...moverPriceFields(item.old_price, item, "old")}
                className="text-muted-foreground"
              />
              <ArrowRight className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
            </>
          ) : null}
          <PriceDisplay {...moverPriceFields(item.new_price, item, "new")} />
        </div>
        <TrendBadge trend={item.direction} value={Math.abs(pct)} size="sm" />
      </div>
    </li>
  );
}

function MoversSkeleton() {
  return (
    <div className="space-y-2" aria-hidden>
      {[1, 2, 3].map((key) => (
        <div key={key} className="flex items-center gap-2 py-2">
          <Skeleton className="h-5 w-16 shrink-0" />
          <Skeleton className="h-4 min-w-0 flex-1" />
          <Skeleton className="h-5 w-28 shrink-0" />
        </div>
      ))}
    </div>
  );
}

function MoversSection({
  title,
  items,
}: {
  title: string;
  items: MoverItem[];
}) {
  if (items.length === 0) {
    return null;
  }
  return (
    <div>
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h4>
      <ul>
        {items.map((item) => (
          <MoverRow
            key={`${item.marketplace_name}-${item.product_name}-${item.changed_at}`}
            item={item}
          />
        ))}
      </ul>
    </div>
  );
}

export interface MarketMoversWidgetProps {
  movementsDataReady: boolean;
  displayCurrency: DisplayCurrency;
  countryCode?: string | null;
}

export function MarketMoversWidget({
  movementsDataReady,
  displayCurrency,
  countryCode = null,
}: MarketMoversWidgetProps) {
  const { t } = useTranslation();

  const moversParams = useMemo(
    (): MovementsQueryParams => ({
      ...MOVERS_LIST_BASE,
      display_currency: displayCurrency,
      country_code: countryCode ?? undefined,
    }),
    [displayCurrency, countryCode],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: marketsQueryKeys.movements(moversParams),
    queryFn: () => marketsApi.getMovers(moversParams).then((response) => response.data),
    staleTime: 30_000,
  });

  const items = data?.items ?? [];
  const showAccumulating = !movementsDataReady || items.length === 0;

  const { gainers, losers } = useMemo(() => {
    const up: MoverItem[] = [];
    const down: MoverItem[] = [];
    for (const item of items) {
      if (item.direction === "up") {
        up.push(item);
      } else {
        down.push(item);
      }
    }
    return { gainers: up, losers: down };
  }, [items]);

  return (
    <div className="surface-base rounded-xl p-3.5">
      <h3 className="mb-3 text-sm font-semibold">{t("market.overview.movements.title")}</h3>

      {isLoading ? (
        <MoversSkeleton />
      ) : isError ? (
        <p className="text-sm text-muted-foreground">{t("market.overview.movements.loadError")}</p>
      ) : showAccumulating ? (
        <EmptyState
          title="market.overview.kpi.accumulatingData"
          description="market.overview.kpi.accumulatingDataHint"
          className="py-8"
        />
      ) : (
        <div className="space-y-4">
          <MoversSection title={t("market.overview.movements.gainers")} items={gainers} />
          <MoversSection title={t("market.overview.movements.losers")} items={losers} />
        </div>
      )}
    </div>
  );
}
