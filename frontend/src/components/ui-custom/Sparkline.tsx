import { Line, LineChart, ResponsiveContainer, Tooltip } from "recharts";

export interface SparklinePoint {
  date?: string;
  price: number;
}

interface SparklineProps {
  points: SparklinePoint[];
  className?: string;
}

function formatSparklineDate(value?: string): string {
  if (!value) {
    return "—";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "short",
  });
}

function formatSparklinePrice(value: number): string {
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

export function Sparkline({ points, className }: SparklineProps) {
  if (points.length < 2) {
    return (
      <div className={className}>
        <div className="flex h-12 items-center justify-center rounded-md border border-dashed border-border text-xs text-muted-foreground">
          Нет истории
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
            formatter={(value: number) => `${formatSparklinePrice(value)} ₽`}
            labelFormatter={(label: string) => formatSparklineDate(label)}
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
