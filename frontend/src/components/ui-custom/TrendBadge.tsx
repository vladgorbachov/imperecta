import { useTranslation } from "react-i18next";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

export type TrendDirection = "up" | "down" | "stable";

export interface TrendBadgeProps {
  /** Price trend direction */
  trend: TrendDirection;
  /** Optional percentage value (e.g. 5.2 for +5.2% or -3.1 for -3.1%) */
  value?: number;
  /** Badge size */
  size?: "sm" | "md";
  /** Additional CSS classes */
  className?: string;
}

/**
 * Badge displaying price trend with icon and optional percentage.
 * Up: red glow | Down: emerald glow | Stable: muted.
 */
export function TrendBadge({ trend, value, size = "md", className }: TrendBadgeProps) {
  const { t } = useTranslation();

  const label =
    trend === "up" && value != null
      ? t("ui.trendPercentPositive", { value: Math.abs(value).toFixed(1) })
      : trend === "down" && value != null
        ? t("ui.trendPercentNegative", { value: Math.abs(value).toFixed(1) })
        : t("ui.trendPercentZero");

  const config = {
    up: {
      icon: TrendingUp,
      style: {
        background: "var(--color-price-up-bg)",
        border: "1px solid var(--color-price-up-border)",
        color: "var(--color-price-up)",
      },
      iconStyle: { filter: "drop-shadow(0 0 4px var(--glow-red))" },
    },
    down: {
      icon: TrendingDown,
      style: {
        background: "rgba(52, 211, 153, 0.15)",
        border: "1px solid rgba(52, 211, 153, 0.3)",
        color: "var(--color-price-down)",
      },
      iconStyle: { filter: "drop-shadow(0 0 4px var(--glow-green))" },
    },
    stable: {
      icon: Minus,
      style: {
        background: "var(--color-muted-bg)",
        border: "1px solid var(--glass-border)",
        color: "var(--foreground-muted)",
      },
      iconStyle: undefined,
    },
  }[trend];

  const Icon = config.icon;
  const sizeClasses = size === "sm" ? "gap-1 px-1.5 py-0 text-xs" : "gap-1.5 px-2 py-0.5 text-sm";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border font-medium",
        sizeClasses,
        className
      )}
      style={config.style}
    >
      <Icon className="size-3.5 shrink-0" style={config.iconStyle} />
      <span>{label}</span>
    </span>
  );
}
