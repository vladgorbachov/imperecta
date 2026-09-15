/**
 * Movements — the price radar: every detected price change with filters.
 * Reads the existing GET /markets/movements endpoint (period, direction,
 * threshold, pagination). Anomaly detection joins this page in Phase 6.
 */

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Activity, TrendingDown, TrendingUp } from "lucide-react";
import {
  marketsApi,
  marketsQueryKeys,
  type MoverItem,
  type MovementsQueryParams,
} from "@/api/markets";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { ErrorState } from "@/components/ui-custom/ErrorState";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useDisplayCurrency } from "@/hooks/useDisplayCurrency";
import { useMarketplaceLabelFormatter } from "@/hooks/useMarketplaceLabel";
import { formatPriceNumber, formatRelativeTime } from "@/lib/formatters";
import { safeNumber } from "@/lib/safeNumber";
import { cn } from "@/lib/utils";
import { useDashboardCountryStore } from "@/stores/dashboardCountryStore";

const PAGE_SIZE = 50;
const PERIODS = ["24h", "7d", "30d"] as const;
const DIRECTIONS = ["all", "up", "down"] as const;
const THRESHOLDS = [0, 1, 3, 5, 10] as const;

/** Static key maps — the i18n coverage guard forbids template-literal keys. */
const PERIOD_LABELS: Record<(typeof PERIODS)[number], string> = {
  "24h": "movements.period.24h",
  "7d": "movements.period.7d",
  "30d": "movements.period.30d",
};
const DIRECTION_LABELS: Record<(typeof DIRECTIONS)[number], string> = {
  all: "movements.direction.all",
  up: "movements.direction.up",
  down: "movements.direction.down",
};

function MoverRow({ item, locale }: { item: MoverItem; locale: string }) {
  const formatMarketplaceLabel = useMarketplaceLabelFormatter();
  const change = safeNumber(item.price_change_pct);
  const isUp = item.direction === "up";
  const newPrice = safeNumber(item.new_price);
  const oldPrice = item.old_price == null ? null : safeNumber(item.old_price);
  const marketplaceLabel = formatMarketplaceLabel({
    name: item.marketplace_name,
    domain: item.marketplace_domain,
    countryCode: item.country_code,
  });

  return (
    <li className="flex items-center gap-3 border-b border-[var(--glass-border)] px-3 py-2.5 last:border-b-0">
      <span
        className={cn(
          "grid size-7 shrink-0 place-items-center rounded-md",
          isUp
            ? "bg-[var(--color-price-up-bg)] text-[var(--color-price-up)]"
            : "bg-[var(--color-price-down-bg)] text-[var(--color-price-down)]",
        )}
        aria-hidden
      >
        {isUp ? <TrendingUp className="size-4" /> : <TrendingDown className="size-4" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{item.product_name}</p>
        <p className="truncate text-xs text-muted-foreground">
          {marketplaceLabel} · {formatRelativeTime(item.changed_at, locale)}
        </p>
      </div>
      <div className="shrink-0 text-right">
        <p className="font-mono text-sm tabular-nums">
          {oldPrice != null ? (
            <span className="text-muted-foreground">
              {formatPriceNumber(oldPrice, locale)} →{" "}
            </span>
          ) : null}
          {formatPriceNumber(newPrice, locale)} {item.currency}
        </p>
        <p
          className={cn(
            "font-mono text-xs font-medium tabular-nums",
            isUp ? "text-[var(--color-price-up)]" : "text-[var(--color-price-down)]",
          )}
        >
          {change > 0 ? "+" : ""}
          {change.toFixed(2)}%
        </p>
      </div>
    </li>
  );
}

export function MovementsPage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const { apiParam: displayCurrency } = useDisplayCurrency();
  const selectedCountry = useDashboardCountryStore((state) => state.selectedCountry);

  const [period, setPeriod] = useState<(typeof PERIODS)[number]>("24h");
  const [direction, setDirection] = useState<(typeof DIRECTIONS)[number]>("all");
  const [threshold, setThreshold] = useState<number>(0);
  const [page, setPage] = useState(1);

  const params = useMemo(
    (): MovementsQueryParams => ({
      period,
      direction,
      threshold: threshold > 0 ? threshold : undefined,
      country_code: selectedCountry ?? undefined,
      display_currency: displayCurrency,
      sort_by: "changed_at",
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [period, direction, threshold, selectedCountry, displayCurrency, page],
  );

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: marketsQueryKeys.movements(params),
    queryFn: () => marketsApi.getMovers(params).then((response) => response.data),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-3">
      <PageHeader title="nav.movements" />

      <div className="surface-base flex flex-wrap items-center gap-2 rounded-lg px-3 py-2">
        <span className="label-mono me-1 hidden sm:inline">{t("movements.filters")}</span>
        <Select value={period} onValueChange={(value) => { setPeriod(value as typeof period); setPage(1); }}>
          <SelectTrigger className="h-9 w-24">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PERIODS.map((value) => (
              <SelectItem key={value} value={value}>
                {t(PERIOD_LABELS[value])}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={direction} onValueChange={(value) => { setDirection(value as typeof direction); setPage(1); }}>
          <SelectTrigger className="h-9 w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DIRECTIONS.map((value) => (
              <SelectItem key={value} value={value}>
                {t(DIRECTION_LABELS[value])}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={String(threshold)}
          onValueChange={(value) => { setThreshold(Number(value)); setPage(1); }}
        >
          <SelectTrigger className="h-9 w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {THRESHOLDS.map((value) => (
              <SelectItem key={value} value={String(value)}>
                {value === 0 ? t("movements.threshold.any") : `≥ ${value}%`}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="surface-base overflow-hidden rounded-xl">
        {isError ? (
          <ErrorState
            title="common.error"
            retry={{ label: "common.refresh", onClick: () => refetch() }}
          />
        ) : isLoading ? (
          <div className="space-y-2 p-4" data-testid="movements-skeleton">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-12 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={Activity}
            title="movements.empty"
            description="movements.emptyHint"
          />
        ) : (
          <ul>
            {items.map((item) => (
              <MoverRow
                key={`${item.product_name}-${item.marketplace_name}-${item.changed_at}`}
                item={item}
                locale={locale}
              />
            ))}
          </ul>
        )}
      </div>

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
          >
            {t("common.back")}
          </Button>
          <span className="px-1 text-sm">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
          >
            {t("common.next")}
          </Button>
        </div>
      )}
    </div>
  );
}
