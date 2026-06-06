import { Line, LineChart, ResponsiveContainer, Tooltip } from "recharts";
import { useTranslation } from "react-i18next";
import { useDisplayCurrency } from "@/hooks/useDisplayCurrency";

export interface SparklinePoint {
  date?: string;
  price: number;
  currency?: string | null;
}

interface SparklineProps {
  points: SparklinePoint[];
  currency?: string | null;
  className?: string;
}

function formatSparklineDate(value: string | undefined, locale: string): string {
  if (!value) {
    return "—";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString(locale, {
    day: "2-digit",
    month: "short",
  });
}

export function Sparkline({ points, currency, className }: SparklineProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const { formatDisplayPrice } = useDisplayCurrency();

  if (points.length < 2) {
    return (
      <div className={className}>
        <div className="flex h-12 items-center justify-center rounded-md border border-dashed border-border text-xs text-muted-foreground">
          {t("market.overview.noHistory")}
        </div>
      </div>
    );
  }

  const first = points[0]?.price ?? 0;
  const last = points[points.length - 1]?.price ?? 0;
  const isUp = last >= first;
  const stroke = isUp ? "var(--color-price-down)" : "var(--color-price-up)";

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={48}>
        <LineChart data={points} margin={{ top: 6, right: 4, left: 4, bottom: 6 }}>
          <Tooltip
            formatter={(value: number, _name: string, item: { payload?: SparklinePoint }) => {
              const pointCurrency = item.payload?.currency ?? currency;
              return formatDisplayPrice({
                localAmount: value,
                localCurrency: pointCurrency,
              });
            }}
            labelFormatter={(label: string) => formatSparklineDate(label, locale)}
            contentStyle={{
              background: "var(--background-elevated)",
              border: "1px solid var(--glass-border)",
              borderRadius: "10px",
              color: "var(--foreground)",
            }}
          />
          <Line
            type="monotone"
            dataKey="price"
            stroke={stroke}
            strokeWidth={2}
            dot={{ r: 2, strokeWidth: 0, fill: stroke }}
            activeDot={{ r: 4 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
