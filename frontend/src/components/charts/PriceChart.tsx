import { useTranslation } from "react-i18next";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { formatChartDate, formatDateTime, formatPrice } from "@/lib/formatters";
import type { PriceHistoryResponse } from "@/api/analytics";

const COMPETITOR_COLORS = [
  "#22c55e",
  "#ef4444",
  "#3b82f6",
  "#f59e0b",
  "#8b5cf6",
  "#ec4899",
  "#06b6d4",
  "#84cc16",
];

interface PriceChartProps {
  data: PriceHistoryResponse | null | undefined;
  isLoading?: boolean;
}

export function PriceChart({ data, isLoading }: PriceChartProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  if (isLoading || !data) {
    return (
      <div className="h-80 animate-pulse rounded-lg border bg-muted" />
    );
  }

  const { my_price, competitors } = data;

  // Build chart data: merge all dates, map prices per series
  const dateSet = new Set<string>();
  const dateToPrices: Record<
    string,
    Record<string, number> & { myPrice: number }
  > = {};

  competitors.forEach((c) => {
    c.data_points.forEach((dp) => {
      const key = new Date(dp.date).toISOString();
      dateSet.add(key);
      if (!dateToPrices[key]) {
        dateToPrices[key] = { myPrice: Number(my_price) };
      }
      dateToPrices[key][c.competitor_name] = Number(dp.price);
    });
  });

  const sortedDates = Array.from(dateSet).sort();
  const chartData = sortedDates.map((d) => ({
    date: d,
    dateLabel: formatChartDate(d, locale),
    myPrice: Number(my_price),
    ...Object.fromEntries(
      competitors.map((c) => [
        c.competitor_name,
        dateToPrices[d]?.[c.competitor_name] ?? null,
      ])
    ),
  }));

  // If no competitor data, show flat my price line
  if (chartData.length === 0) {
    chartData.push({
      date: new Date().toISOString(),
      dateLabel: formatChartDate(new Date(), locale),
      myPrice: Number(my_price),
      ...Object.fromEntries(competitors.map((c) => [c.competitor_name, null])),
    });
  }

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted dark:stroke-muted" />
          <XAxis
            dataKey="dateLabel"
            tick={{ fontSize: 12 }}
            stroke="hsl(var(--muted-foreground))"
          />
          <YAxis
            tick={{ fontSize: 12 }}
            stroke="hsl(var(--muted-foreground))"
            tickFormatter={(v) => formatPrice(v, "RUB", locale)}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "6px",
            }}
            labelFormatter={(_, payload) =>
              payload?.[0]?.payload?.date
                ? formatDateTime(payload[0].payload.date, locale)
                : ""
            }
            formatter={(value: number) => [value != null ? formatPrice(value, "RUB", locale) : t("common.dash"), ""]}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="myPrice"
            name={t("productDetail.myPriceLegend")}
            stroke="hsl(99 102 241)"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
            connectNulls
          />
          {competitors.map((c, i) => (
            <Line
              key={c.competitor_product_id}
              type="monotone"
              dataKey={c.competitor_name}
              name={c.competitor_name}
              stroke={COMPETITOR_COLORS[i % COMPETITOR_COLORS.length]}
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
