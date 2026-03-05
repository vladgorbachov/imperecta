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
 * Up: red background, pulse; Down: emerald, pulse; Stable: muted.
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
      classes:
        "bg-price-up/15 text-price-up dark:bg-price-up/20 dark:text-price-up border-price-up/30 animate-pulse",
    },
    down: {
      icon: TrendingDown,
      classes:
        "bg-price-down/15 text-price-down dark:bg-price-down/20 dark:text-price-down border-price-down/30 animate-pulse",
    },
    stable: {
      icon: Minus,
      classes:
        "bg-muted text-muted-foreground dark:bg-muted/80 dark:text-muted-foreground border-border",
    },
  }[trend];

  const Icon = config.icon;
  const sizeClasses = size === "sm" ? "gap-1 px-1.5 py-0 text-xs" : "gap-1.5 px-2 py-0.5 text-sm";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border font-medium",
        config.classes,
        sizeClasses,
        className
      )}
    >
      <Icon className="size-3.5 shrink-0" />
      <span>{label}</span>
    </span>
  );
}
