// MOBILE-2026: fully responsive + bottom nav + drawer

/**
 * KPI Overview: 4 cards with glass effect, glassmorphism on mobile.
 * Data from GET /api/analytics/dashboard/summary
 */

import { useTranslation } from "react-i18next";
import { Package, TrendingUp, Bell, DollarSign, ChevronUp, ChevronDown } from "lucide-react";
import { motion } from "framer-motion";
import { useDashboardSummary, useDashboardKpi } from "@/hooks/useDashboard";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.05, duration: 0.3 },
  }),
};

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
        <motion.div
          key={card.key}
          custom={i}
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          className={cn(
            "rounded-xl border border-border bg-card/80 p-4 shadow-sm backdrop-blur-sm transition-transform hover:scale-[1.02] active:scale-[0.98] dark:border-border",
            "dark:bg-card/90"
          )}
        >
          <div className="flex items-start justify-between">
            <card.icon className="size-5 text-muted-foreground" />
            {card.trend != null && (
              <span
                className={cn(
                  "flex items-center text-xs font-medium",
                  card.trendUp ? "text-price-down" : "text-price-up"
                )}
              >
                {card.trendUp ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                {Math.abs(card.trend).toFixed(1)}%
              </span>
            )}
          </div>
          <p className="mt-2 text-sm text-muted-foreground">{card.title}</p>
          <p className="mt-1 text-3xl font-bold text-foreground">
            {typeof card.value === "number" && !card.isPercent
              ? new Intl.NumberFormat(locale).format(card.value)
              : card.value}
            {card.suffix ?? ""}
          </p>
          {(card.badge || card.subtitle) && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {card.subtitle && (
                <span className="text-xs text-muted-foreground">{card.subtitle}</span>
              )}
              {card.badge && (
                <span className="rounded-md bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary">
                  {card.badge}
                </span>
              )}
            </div>
          )}
        </motion.div>
      ))}
    </div>
  );
}
