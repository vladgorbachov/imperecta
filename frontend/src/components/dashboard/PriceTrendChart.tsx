/**
 * Price trend chart with Recharts.
 * Data: GET /api/dashboard/aggregate-trend
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Area,
  Line,
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Download } from "lucide-react";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/api/analytics";
import { formatChartDate } from "@/lib/formatters";
import { Button } from "@/components/ui/button";

type Period = "7d" | "30d" | "90d";

const PERIOD_DAYS: Record<Period, number> = { "7d": 7, "30d": 30, "90d": 90 };

export function PriceTrendChart() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const [period, setPeriod] = useState<Period>("30d");

  const days = PERIOD_DAYS[period];
  const { data: trendData, isLoading } = useQuery({
    queryKey: ["dashboard", "aggregate-trend", days],
    queryFn: async () => {
      const { data } = await analyticsApi.getAggregateTrend(days, 7);
      return data;
    },
  });

  const chartData = trendData
    ? [
        ...trendData.labels.map((date, i) => ({
          date,
          dateLabel: formatChartDate(new Date(date), locale),
          myAvg: trendData.my_products_avg[i] ?? 0,
          competitorAvg: trendData.competitors_avg[i] ?? 0,
          forecast: null as number | null,
          isForecast: false,
        })),
        ...(trendData.forecast_labels ?? []).map((date, i) => ({
          date,
          dateLabel: formatChartDate(new Date(date), locale),
          myAvg: 0,
          competitorAvg: 0,
          forecast: trendData.forecast[i] ?? null,
          isForecast: true,
        })),
      ]
    : [];

  const handleDownloadCsv = () => {
    if (!chartData.length) return;
    const headers = ["date", "myAvg", "competitorAvg", "forecast"];
    const rows = chartData.map((r) =>
      [r.date, r.myAvg, r.competitorAvg, r.forecast ?? ""].join(",")
    );
    const csv = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `price-trend-${period}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="h-[280px] w-full rounded-xl border border-border bg-card p-4 shadow-sm sm:h-[350px] md:h-[400px] dark:border-border"
      >
        <div className="mb-4 flex gap-2">
          <div className="h-9 w-14 animate-pulse rounded-md bg-muted" />
          <div className="h-9 w-14 animate-pulse rounded-md bg-muted" />
          <div className="h-9 w-14 animate-pulse rounded-md bg-muted" />
        </div>
        <div className="flex h-[calc(100%-48px)] flex-col gap-2">
          <div className="h-full min-h-[180px] animate-pulse rounded-lg bg-muted" />
        </div>
      </motion.div>
    );
  }

  if (!chartData.length || chartData.every((d) => !d.myAvg && !d.competitorAvg && !d.forecast)) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="h-[280px] w-full rounded-xl border border-border bg-card p-4 shadow-sm sm:h-[350px] md:h-[400px] dark:border-border"
      >
        <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
          <p>{t("dashboard.chart.noData")}</p>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1, duration: 0.3 }}
      className="h-[280px] w-full rounded-xl border border-border bg-card p-4 shadow-sm sm:h-[350px] md:h-[400px] dark:border-border"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-2">
          {(["7d", "30d", "90d"] as const).map((p) => (
            <Button
              key={p}
              variant={period === p ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriod(p)}
            >
              {p === "7d" ? "7d" : p === "30d" ? "30d" : "90d"}
            </Button>
          ))}
        </div>
        <Button variant="outline" size="sm" onClick={handleDownloadCsv}>
          <Download className="me-2 size-4" />
          {t("dashboard.chart.downloadCsv")}
        </Button>
      </div>
      <ResponsiveContainer width="100%" height="calc(100% - 48px)">
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="forecastGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
              <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis
            dataKey="dateLabel"
            tick={{ fontSize: 11 }}
            stroke="var(--muted-foreground)"
          />
          <YAxis
            tick={{ fontSize: 11 }}
            stroke="var(--muted-foreground)"
            tickFormatter={(v) => new Intl.NumberFormat(locale).format(v)}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload;
              const diff = p.myAvg && p.competitorAvg
                ? ((p.myAvg - p.competitorAvg) / p.competitorAvg) * 100
                : 0;
              return (
                <div className="rounded-lg border border-border bg-card p-3 shadow-lg">
                  <p className="text-sm font-medium">{p.dateLabel}</p>
                  <p className="text-xs text-muted-foreground">
                    {t("dashboard.chart.myProducts")}: {new Intl.NumberFormat(locale).format(p.myAvg)} ₽
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {t("dashboard.chart.competitors")}: {new Intl.NumberFormat(locale).format(p.competitorAvg)} ₽
                  </p>
                  <p className="text-xs font-medium">
                    {t("dashboard.chart.diffPercent")}: {diff > 0 ? "+" : ""}{diff.toFixed(1)}%
                  </p>
                </div>
              );
            }}
          />
          <Legend />
          <Area
            type="monotone"
            dataKey="forecast"
            stroke="hsl(var(--primary))"
            strokeDasharray="4 4"
            fill="url(#forecastGradient)"
            name={t("dashboard.chart.forecast")}
            connectNulls
          />
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
    </motion.div>
  );
}
