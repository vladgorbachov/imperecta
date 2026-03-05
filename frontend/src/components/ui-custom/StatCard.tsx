import type { LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
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
 * Dashboard stat card with large value, optional icon, TrendBadge, and loading state.
 * Responsive: full-width mobile, 4-col grid desktop. Hover: subtle border transition.
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
    <Card
      style={style}
      className={cn(
        "transition-colors hover:border-primary/30 dark:hover:border-primary/40",
        "w-full min-w-0",
        className
      )}
    >
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        {isLoading ? (
          <Skeleton className="h-4 w-24" />
        ) : (
          <p className="text-sm font-medium text-muted-foreground dark:text-muted-foreground">
            {t(title)}
          </p>
        )}
        {Icon && !isLoading && (
          <Icon className="size-4 shrink-0 text-muted-foreground dark:text-muted-foreground" />
        )}
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-8 w-16" />
        ) : (
          <div className="flex flex-col gap-2">
            <div className="text-2xl font-bold">{value}</div>
            {badges && badges.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {badges.map((b, i) => (
                  <TrendBadge
                    key={i}
                    trend={b.direction}
                    value={b.value}
                    size="sm"
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
