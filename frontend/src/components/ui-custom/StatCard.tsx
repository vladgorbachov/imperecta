import type { LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { TrendBadge } from "./TrendBadge";
import { cn } from "@/lib/utils";

export type TrendDirection = "up" | "down" | "stable";

export interface StatCardProps {
  /** i18n key for card title */
  title: string;
  /** Display value (number or string) */
  value: number | string;
  /** Optional trend indicator */
  trend?: { direction: TrendDirection; value?: number };
  /** Optional multiple trend badges (e.g. price changes: up 12, down 11) */
  trendBadges?: Array<{ direction: TrendDirection; value?: number }>;
  /** Optional icon in top-right */
  icon?: LucideIcon;
  /** Show skeleton instead of content */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Inline styles (e.g. animationDelay for stagger) */
  style?: React.CSSProperties;
}

/**
 * Dashboard stat card with glassmorphism design.
 * Ambient glow, display font value, TrendBadge, shimmer loading.
 */
export function StatCard({
  title,
  value,
  trend,
  trendBadges,
  icon: Icon,
  isLoading = false,
  className,
  style,
}: StatCardProps) {
  const { t } = useTranslation();
  const badges = trendBadges ?? (trend ? [trend] : undefined);

  return (
    <div
      style={style}
      className={cn(
        "glass-card relative overflow-hidden rounded-xl p-5",
        isLoading && "shimmer",
        className
      )}
    >
      {/* Ambient glow blob — positioned top-right */}
      <div
        className="absolute -top-8 -right-8 h-24 w-24 rounded-full opacity-20 blur-2xl"
        style={{ background: "var(--accent)" }}
      />

      {/* Top row: title + icon */}
      <div className="mb-3 flex items-center justify-between">
        {isLoading ? (
          <div className="h-4 w-24 animate-pulse rounded bg-[var(--glass-bg)]" />
        ) : (
          <span
            className="text-xs font-medium uppercase tracking-wider"
            style={{ color: "var(--foreground-muted)" }}
          >
            {t(title)}
          </span>
        )}
        {Icon && !isLoading && (
          <div
            className="rounded-lg border p-2"
            style={{
              background: "var(--glass-bg)",
              borderColor: "var(--glass-border)",
            }}
          >
            <Icon
              className="size-4"
              style={{
                color: "var(--accent)",
                filter: "drop-shadow(0 0 6px var(--accent-glow))",
              }}
            />
          </div>
        )}
      </div>

      {/* Value — large, display font */}
      {isLoading ? (
        <div className="mb-2 h-8 w-16 animate-pulse rounded bg-[var(--glass-bg)]" />
      ) : (
        <div
          className="text-3xl font-bold"
          style={{ color: "var(--foreground)", fontFamily: "var(--font-display)" }}
        >
          {value}
        </div>
      )}

      {/* Trend badge */}
      {badges && badges.length > 0 && !isLoading && (
        <div className="mt-2 flex flex-wrap gap-1">
          {badges.map((b, i) => (
            <TrendBadge key={i} trend={b.direction} value={b.value} size="sm" />
          ))}
        </div>
      )}

      {/* Bottom accent line */}
      <div className="accent-line absolute bottom-0 left-0 right-0" />
    </div>
  );
}
