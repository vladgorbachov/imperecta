/**
 * KPI Overview: 4 cards with glass effect, stagger entrance animation.
 * Data from GET /api/analytics/dashboard/summary
 */

import { useTranslation } from "react-i18next";
import { Package, TrendingUp, Bell, DollarSign, ChevronUp, ChevronDown } from "lucide-react";
import { useDashboardSummary, useDashboardKpi } from "@/hooks/useDashboard";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const STAGGER_DELAYS = [0, 100, 200, 300];

export function KPIOverview() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const { data: summary, isLoading, isError } = useDashboardSummary();
  const { data: kpi } = useDashboardKpi();

  const avgPriceChange24h = kpi?.avg_price_change_24h ?? (summary?.price_changes_today
    ? (summary.price_changes_today.increases - summary.price_changes_today.drops) * 0.5
    : 0);
  const revenueImpact = kpi?.revenue_impact_percent ?? 0;
  const revenueConfidence = Math.round((kpi?.revenue_impact_confidence ?? 0) * 100);
  const criticalAlerts = Math.min(3, kpi?.critical_alerts_count ?? summary?.alerts_triggered_today ?? 0);
  const weekTrend = kpi?.trend_vs_last_week?.price_change;

  const cards = [
    {
      key: "totalProducts",
      icon: Package,
      title: t("dashboard.kpi.totalProducts"),
      value: summary?.total_products ?? 0,
      trend: weekTrend,
      trendUp: (weekTrend ?? 0) >= 0,
    },
    {
      key: "avgPriceChange",
      icon: TrendingUp,
      title: t("dashboard.kpi.avgPriceChange"),
      value: avgPriceChange24h,
      suffix: "%",
      isPercent: true,
      trendUp: avgPriceChange24h >= 0,
    },
    {
      key: "activeAlerts",
      icon: Bell,
      title: t("dashboard.kpi.activeAlerts"),
      value: summary?.alerts_triggered_today ?? 0,
      badge: criticalAlerts > 0 ? t("dashboard.kpi.criticalCount", { count: criticalAlerts }) : undefined,
    },
    {
      key: "revenueImpact",
      icon: DollarSign,
      title: t("dashboard.kpi.revenueImpact"),
      value: `+${revenueImpact}%`,
      subtitle: t("dashboard.kpi.predicted"),
      badge: `${revenueConfidence}%`,
    },
  ];

  if (isLoading || isError) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28 rounded-xl animate-pulse sm:h-32" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
      {cards.map((card, i) => (
        <div
          key={card.key}
          className={cn(
            "glass-card flex flex-col rounded-xl p-4 transition-transform hover:scale-[1.02] active:scale-[0.98]",
            "animate-fade-slide-up"
          )}
          style={{
            animationDelay: `${STAGGER_DELAYS[i]}ms`,
            animationFillMode: "forwards",
          }}
        >
          <div className="flex items-start justify-between">
            <card.icon className="size-5" style={{ color: "var(--foreground-muted)" }} />
            {card.trend != null && (
              <span
                className={cn(
                  "flex items-center text-xs font-medium",
                  card.trendUp ? "text-[var(--color-price-down)]" : "text-[var(--color-price-up)]"
                )}
              >
                {card.trendUp ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                {Math.abs(card.trend).toFixed(1)}%
              </span>
            )}
          </div>
          <p className="mt-2 text-sm" style={{ color: "var(--foreground-muted)" }}>
            {card.title}
          </p>
          <p
            className="mt-1 text-3xl font-bold"
            style={{ color: "var(--foreground)", fontFamily: "var(--font-display)" }}
          >
            {typeof card.value === "number" && !card.isPercent
              ? new Intl.NumberFormat(locale).format(card.value)
              : card.value}
            {card.suffix ?? ""}
          </p>
          {(card.badge || card.subtitle) && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {card.subtitle && (
                <span className="text-xs" style={{ color: "var(--foreground-muted)" }}>
                  {card.subtitle}
                </span>
              )}
              {card.badge && (
                <span
                  className="rounded-md px-2 py-0.5 text-xs font-medium"
                  style={{
                    background: "var(--accent-bg)",
                    color: "var(--accent)",
                  }}
                >
                  {card.badge}
                </span>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
