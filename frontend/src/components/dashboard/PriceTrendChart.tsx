/**
 * Price trend chart with Recharts.
 * Data: GET /api/analytics/products/aggregate-trend
 * TODO: create endpoint. Mock 37 data points (30 days + 7 forecast).
 */

import { useState, useMemo } from "react";
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
import { Button } from "@/components/ui/button";
import { formatChartDate } from "@/lib/formatters";

// TODO: create GET /api/analytics/products/aggregate-trend
function generateMockData(period: "7d" | "30d" | "90d", locale: string): Array<{
  date: string;
  dateLabel: string;
  myAvg: number;
  competitorAvg: number;
  forecast: number | null;
  isForecast?: boolean;
}> {
  const days = period === "7d" ? 7 : period === "30d" ? 30 : 90;
  const forecastDays = 7;
  const data: Array<{
    date: string;
    dateLabel: string;
    myAvg: number;
    competitorAvg: number;
    forecast: number | null;
    isForecast?: boolean;
  }> = [];
  const basePrice = 45000;
  const now = new Date();

  for (let i = -days; i <= forecastDays; i++) {
    const d = new Date(now);
    d.setDate(d.getDate() + i);
    const dateStr = d.toISOString().slice(0, 10);
    const isForecast = i > 0;
    const noise = () => (Math.random() - 0.5) * 2000;
    const trend = i * 50;
    data.push({
      date: dateStr,
      dateLabel: formatChartDate(d, locale),
      myAvg: Math.round(basePrice + trend + noise() + (isForecast ? i * 30 : 0)),
      competitorAvg: Math.round(basePrice * 0.95 + trend * 0.8 + noise()),
      forecast: isForecast ? Math.round(basePrice + trend + i * 40 + noise()) : null,
      isForecast,
    });
  }
  return data;
}

type Period = "7d" | "30d" | "90d";

export function PriceTrendChart() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const [period, setPeriod] = useState<Period>("30d");

  const chartData = useMemo(() => generateMockData(period, locale), [period, locale]);

  const handleDownloadCsv = () => {
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

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1, duration: 0.3 }}
      className="h-[400px] rounded-xl border border-border/50 bg-card/60 p-4 shadow-sm backdrop-blur-lg dark:bg-zinc-900/60 dark:border-border/50"
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
            stroke="hsl(var(--muted-foreground))"
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
