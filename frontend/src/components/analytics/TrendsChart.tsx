/**
 * Multi-line ComposedChart: my products, competitors, seasonality Area.
 * TODO: GET /api/analytics/trends
 */

import { useMemo } from "react";
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
import { formatChartDate } from "@/lib/formatters";
import { CHART_PRIMARY, CHART_COLORS } from "@/lib/design-tokens";

type Period = "7d" | "30d" | "90d";

interface TrendsChartProps {
  period: Period;
  category: string;
  competitorIds: string[];
  products: { id: string; name: string }[];
  competitors: { id: string; name: string }[];
}

function generateMockTrendData(
  period: Period,
  locale: string,
  productNames: string[],
  competitorNames: string[]
): Array<Record<string, string | number | null>> {
  const days = period === "7d" ? 7 : period === "30d" ? 30 : 90;
  const data: Array<Record<string, string | number | null>> = [];
  const basePrice = 45000;
  const now = new Date();

  for (let i = -days; i <= 0; i++) {
    const d = new Date(now);
    d.setDate(d.getDate() + i);
    const dateStr = d.toISOString().slice(0, 10);
    const seasonMult = 0.95 + Math.sin((i / 30) * Math.PI * 2) * 0.1;
    const point: Record<string, string | number | null> = {
      date: dateStr,
      dateLabel: formatChartDate(d, locale),
      seasonality: Math.round(basePrice * seasonMult),
    };

    const trend = i * 40;
    const noise = () => (Math.random() - 0.5) * 1500;

    productNames.forEach((_, pi) => {
      point[`my_${pi}`] = Math.round(basePrice + pi * 500 + trend + noise());
    });
    competitorNames.forEach((_, ci) => {
      point[`comp_${ci}`] = Math.round(basePrice * 0.92 + ci * 300 + trend * 0.9 + noise());
    });

    data.push(point);
  }
  return data;
}

export function TrendsChart({
  period,
  category: _category,
  competitorIds,
  products,
  competitors,
}: TrendsChartProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;

  const productNames = products.map((p) => p.name);
  const filteredCompetitors = competitors.filter((c) => competitorIds.includes(c.id));
  const competitorNames = filteredCompetitors.map((c) => c.name);

  const chartData = useMemo(
    () => generateMockTrendData(period, locale, productNames, competitorNames),
    [period, locale, productNames, competitorNames]
  );

  const myKeys = productNames.map((_, i) => `my_${i}`);
  const compKeys = competitorNames.map((_, i) => `comp_${i}`);

  return (
    <div className="h-[500px] w-full rounded-lg border border-border bg-card/60 p-4 dark:border-border dark:bg-card/60">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="seasonalityGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--muted-foreground))" stopOpacity={0.2} />
              <stop offset="100%" stopColor="hsl(var(--muted-foreground))" stopOpacity={0} />
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
          <Area
            type="monotone"
            dataKey="seasonality"
            stroke="none"
            fill="url(#seasonalityGrad)"
            name={t("analytics.seasonality")}
            fillOpacity={0.5}
          />
          {myKeys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={CHART_PRIMARY}
              strokeWidth={i === 0 ? 2 : 1.5}
              strokeDasharray={i > 0 ? "4 4" : undefined}
              dot={false}
              name={productNames[i] ?? t("analytics.myProducts")}
            />
          ))}
          {compKeys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={CHART_COLORS[i % CHART_COLORS.length]}
              strokeWidth={1.5}
              dot={false}
              name={competitorNames[i]}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
