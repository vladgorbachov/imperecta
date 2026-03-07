/**
 * Aggregate trend chart: my products avg vs competitors avg.
 * Data: GET /api/dashboard/aggregate-trend
 */

import { useTranslation } from "react-i18next";
import {
  Line,
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/api/analytics";
import { formatChartDate } from "@/lib/formatters";

type Period = "7d" | "30d" | "90d";

const PERIOD_DAYS: Record<Period, number> = { "7d": 7, "30d": 30, "90d": 90 };

interface TrendsChartProps {
  period: Period;
  category: string;
  competitorIds: string[];
  products: { id: string; name: string }[];
  competitors: { id: string; name: string }[];
}

export function TrendsChart({
  period,
  category: _category,
  competitorIds: _competitorIds,
  products: _products,
  competitors: _competitors,
}: TrendsChartProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const days = PERIOD_DAYS[period];

  const { data: trendData, isLoading } = useQuery({
    queryKey: ["dashboard", "aggregate-trend", days],
    queryFn: async () => {
      const { data } = await analyticsApi.getAggregateTrend(days, 0);
      return data;
    },
  });

  const chartData =
    trendData?.labels?.map((date, i) => ({
      date,
      dateLabel: formatChartDate(new Date(date), locale),
      myAvg: trendData.my_products_avg[i] ?? 0,
      competitorAvg: trendData.competitors_avg[i] ?? 0,
    })) ?? [];

  if (isLoading) {
    return (
      <div className="flex h-[500px] w-full items-center justify-center rounded-lg border border-border bg-card p-4 dark:border-border dark:bg-card">
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      </div>
    );
  }

  if (!chartData.length || chartData.every((d) => !d.myAvg && !d.competitorAvg)) {
    return (
      <div className="flex h-[500px] w-full items-center justify-center rounded-lg border border-border bg-card p-4 dark:border-border dark:bg-card">
        <p className="text-sm text-muted-foreground">{t("analytics.noForecastData")}</p>
      </div>
    );
  }

  return (
    <div className="h-[500px] w-full rounded-lg border border-border bg-card p-4 dark:border-border dark:bg-card">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis
            dataKey="dateLabel"
            tick={{ fontSize: 11 }}
            stroke="hsl(var(--muted-foreground))"
          />
          <YAxis
            tick={{ fontSize: 11 }}
            stroke="hsl(var(--muted-foreground))"
            tickFormatter={(v) => new Intl.NumberFormat(locale).format(v)}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0]?.payload as Record<string, unknown>;
              return (
                <div className="rounded-lg border border-border bg-card p-3 shadow-lg">
                  <p className="mb-2 text-sm font-medium">{String(p.dateLabel)}</p>
                  <div className="space-y-1 text-xs">
                    {payload.map((item) => (
                      <p key={String(item.dataKey)}>
                        {item.name}: {item.value != null ? new Intl.NumberFormat(locale).format(Number(item.value)) : "—"}
                      </p>
                    ))}
                  </div>
                </div>
              );
            }}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="myAvg"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={false}
            name={t("dashboard.chart.myProducts")}
          />
          <Line
            type="monotone"
            dataKey="competitorAvg"
            stroke="var(--muted-foreground)"
            strokeWidth={1.5}
            strokeDasharray="5 5"
            dot={false}
            name={t("dashboard.chart.competitors")}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
