/**
 * Mini sparkline for price aggressiveness over 30 days.
 * Uses Recharts AreaChart without axes.
 */

import { Area, AreaChart, ResponsiveContainer } from "recharts";

interface PriceSparklineProps {
  data: number[];
  className?: string;
}

export function PriceSparkline({ data, className }: PriceSparklineProps) {
  const chartData = data.map((v, i) => ({ value: v, index: i }));

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={40}>
        <AreaChart data={chartData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
          <defs>
            <linearGradient id="sparklineGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.4} />
              <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke="hsl(var(--primary))"
            strokeWidth={1.5}
            fill="url(#sparklineGrad)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
