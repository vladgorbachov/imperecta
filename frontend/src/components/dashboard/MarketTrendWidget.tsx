import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { LineChart } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";
import {
  marketsApi,
  marketsQueryKeys,
  type TrendPoint,
  type TrendParams,
} from "@/api/markets";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { CHART_PRIMARY } from "@/lib/design-tokens";
import { formatChartDate, formatPriceNumber } from "@/lib/formatters";
import { cn } from "@/lib/utils";

type TrendPeriod = NonNullable<TrendParams["period"]>;

const PERIOD_OPTIONS: TrendPeriod[] = ["7d", "30d", "90d"];

function parseAvgPriceEur(value: number | string | null | undefined): number | null {
  if (value == null || value === "") {
    return null;
  }
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

interface ChartRow {
  bucket_start: string;
  bucket_label: string;
  avg_price_eur: number | null;
  sample_size: number;
}

function toChartRow(point: TrendPoint): ChartRow {
  const sampleSize = point.sample_size ?? 0;
  return {
    bucket_start: point.bucket_start,
    bucket_label: point.bucket_label,
    sample_size: sampleSize,
    avg_price_eur:
      sampleSize > 0 ? parseAvgPriceEur(point.avg_price_eur) : null,
  };
}

function periodLabel(period: TrendPeriod, t: (key: string) => string): string {
  if (period === "7d") {
    return t("productDetail.period7d");
  }
  if (period === "90d") {
    return t("productDetail.period90d");
  }
  return t("market.overview.thirtyDayChart");
}

function TrendSkeleton() {
  return (
    <div className="space-y-3" data-testid="trend-skeleton">
      <Skeleton className="h-[200px] w-full rounded-md" />
    </div>
  );
}

function TrendChartTooltip({
  active,
  payload,
  label,
}: TooltipProps<number, string>) {
  const { t, i18n } = useTranslation();
  if (!active || !payload?.length) {
    return null;
  }
  const row = payload[0]?.payload as ChartRow | undefined;
  if (!row || row.sample_size <= 0 || row.avg_price_eur == null) {
    return null;
  }
  const dateLabel =
    typeof label === "string" ? label : row.bucket_start;
  return (
    <div className="surface-base rounded-md border border-border/60 px-2.5 py-2 text-xs shadow-sm">
      <p className="text-muted-foreground">
        {formatChartDate(dateLabel, i18n.language)}
      </p>
      <p className="mt-0.5 font-medium tabular-nums">
        {formatPriceNumber(row.avg_price_eur, i18n.language)} EUR
      </p>
      <p className="mt-0.5 text-muted-foreground">
        {t("market.overview.trend.sampleSize", { count: row.sample_size })}
      </p>
    </div>
  );
}

export interface MarketTrendWidgetProps {
  countryCode: string | null;
  marketplaceId?: string;
}

export function MarketTrendWidget({
  countryCode,
  marketplaceId,
}: MarketTrendWidgetProps) {
  const { t, i18n } = useTranslation();
  const [period, setPeriod] = useState<TrendPeriod>("30d");
  const bucket: TrendParams["bucket"] = "day";

  const queryParams = useMemo(
    () => ({
      period,
      bucket,
      country_code: countryCode ?? undefined,
      marketplace_id: marketplaceId,
    }),
    [period, bucket, countryCode, marketplaceId],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: marketsQueryKeys.trend(queryParams),
    queryFn: () => marketsApi.getTrend(queryParams).then((response) => response.data),
    staleTime: 30_000,
  });

  const chartRows = useMemo(
    () => (data?.points ?? []).map(toChartRow),
    [data?.points],
  );

  const plottableCount = useMemo(
    () => chartRows.filter((row) => row.sample_size > 0 && row.avg_price_eur != null).length,
    [chartRows],
  );

  const showChart =
    !isLoading &&
    !isError &&
    data?.data_ready === true &&
    plottableCount >= 2;

  const showEmpty =
    !isLoading && !isError && !showChart;

  return (
    <div className="surface-base flex h-full min-w-0 flex-col rounded-xl p-3.5">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">{t("market.overview.trend.title")}</h3>
          <p className="mt-0.5 text-2xs text-muted-foreground">
            {t("market.overview.trend.subtitle")}
          </p>
        </div>
        <div
          className="flex shrink-0 gap-0.5 rounded-lg border border-border/60 p-0.5"
          role="group"
          aria-label={t("market.overview.trend.title")}
        >
          {PERIOD_OPTIONS.map((option) => (
            <Button
              key={option}
              type="button"
              variant="ghost"
              size="sm"
              className={cn(
                "h-7 px-2.5 text-2xs",
                period === option && "bg-muted font-medium text-foreground",
              )}
              onClick={() => setPeriod(option)}
            >
              {periodLabel(option, t)}
            </Button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <TrendSkeleton />
      ) : isError ? (
        <p className="text-sm text-muted-foreground">{t("market.overview.trend.loadError")}</p>
      ) : showEmpty ? (
        <EmptyState
          title="market.overview.trend.empty"
          description="market.overview.trend.emptyHint"
          icon={LineChart}
          className="py-8"
        />
      ) : showChart ? (
        <div className="min-h-[200px] min-w-0 w-full" data-testid="trend-chart">
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={chartRows} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border/40" />
              <XAxis
                dataKey="bucket_start"
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                minTickGap={24}
                tickFormatter={(value: string) => formatChartDate(value, i18n.language)}
              />
              <YAxis
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={52}
                tickFormatter={(value: number) => formatPriceNumber(value, i18n.language)}
              />
              <Tooltip content={<TrendChartTooltip />} />
              <Area
                type="monotone"
                dataKey="avg_price_eur"
                stroke={CHART_PRIMARY}
                fill={CHART_PRIMARY}
                fillOpacity={0.12}
                strokeWidth={2}
                connectNulls={false}
                dot={false}
                activeDot={{ r: 3, fill: CHART_PRIMARY }}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
          <p className="mt-1 text-right text-2xs text-muted-foreground">EUR</p>
        </div>
      ) : null}
    </div>
  );
}
