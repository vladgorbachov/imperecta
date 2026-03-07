/**
 * Dashboard page with stats, top changes table, active promos, anomalies.
 * All data from API: analyticsApi.getDashboardSummary, getDashboardAnomalies.
 */

import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Package,
  Users,
  Bell,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";
import { formatChartDate, formatPrice, formatRelativeTime } from "@/lib/formatters";
import { StatCard } from "@/components/ui-custom/StatCard";
import { PriceChangeCell } from "@/components/ui-custom/PriceChangeCell";
import { TrendBadge } from "@/components/ui-custom/TrendBadge";
import { MarketplaceBadge } from "@/components/ui-custom/MarketplaceBadge";
import { PromoBadge } from "@/components/ui-custom/PromoBadge";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useDashboardSummary, useDashboardAnomalies } from "@/hooks/useDashboard";

type Marketplace = "ozon" | "wildberries" | "kaspi" | "custom";

function competitorNameToMarketplace(name: string): Marketplace {
  const lower = name.toLowerCase();
  if (lower.includes("ozon")) return "ozon";
  if (lower.includes("wildberries") || lower.includes("wb")) return "wildberries";
  if (lower.includes("kaspi")) return "kaspi";
  return "custom";
}

export function DashboardPage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const queryClient = useQueryClient();

  const { data: summary, isLoading: summaryLoading, refetch: refetchSummary } = useDashboardSummary();
  const { data: anomalies = [], isLoading: anomaliesLoading, refetch: refetchAnomalies } = useDashboardAnomalies();

  const handleRefresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard", "anomalies"] }),
    ]);
    await Promise.all([refetchSummary(), refetchAnomalies()]);
  };

  const isLoading = summaryLoading;
  const updatedTime = summary?.last_scrape_at
    ? formatRelativeTime(summary.last_scrape_at, locale)
    : null;

  const topChanges = summary?.top_changes ?? [];
  const activePromos = summary?.active_promos ?? [];
  const priceChanges = summary?.price_changes_today ?? { drops: 0, increases: 0 };
  const priceChangesTotal = priceChanges.drops + priceChanges.increases;

  return (
    <div className="space-y-6">
      <PageHeader title="nav.dashboard" />

      {/* Stats row */}
      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="dashboard.products"
          value={summary?.total_products ?? 0}
          icon={Package}
          isLoading={isLoading}
          className="animate-in fade-in-0 slide-in-from-bottom-2 fill-mode-both"
          style={{ animationDelay: "0ms" }}
        />
        <StatCard
          title="dashboard.competitors"
          value={summary?.total_competitors ?? 0}
          icon={Users}
          isLoading={isLoading}
          className="animate-in fade-in-0 slide-in-from-bottom-2 fill-mode-both"
          style={{ animationDelay: "100ms" }}
        />
        <StatCard
          title="dashboard.alertsToday"
          value={summary?.alerts_triggered_today ?? 0}
          icon={Bell}
          isLoading={isLoading}
          className="animate-in fade-in-0 slide-in-from-bottom-2 fill-mode-both"
          style={{ animationDelay: "200ms" }}
        />
        <StatCard
          title="dashboard.priceChanges"
          value={priceChangesTotal}
          trendBadges={[
            { direction: "up", value: priceChanges.increases },
            { direction: "down", value: priceChanges.drops },
          ]}
          isLoading={isLoading}
          className="animate-in fade-in-0 slide-in-from-bottom-2 fill-mode-both"
          style={{ animationDelay: "300ms" }}
        />
      </section>

      {/* Top 5 changes */}
      <section className="animate-in fade-in-0 slide-in-from-bottom-2 fill-mode-both delay-100">
        <Card>
          <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle>{t("dashboard.topChangesToday")}</CardTitle>
            <div className="flex items-center gap-2">
              {updatedTime && (
                <span className="text-sm text-muted-foreground dark:text-muted-foreground">
                  {t("dashboard.updatedAgo", { time: updatedTime })}
                </span>
              )}
              <Button
                variant="ghost"
                size="icon"
                onClick={handleRefresh}
                disabled={isLoading}
                aria-label={t("common.refresh")}
              >
                <RefreshCw className={cn("size-4", isLoading && "animate-spin")} />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              {isLoading ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("dashboard.product")}</TableHead>
                      <TableHead>{t("dashboard.competitor")}</TableHead>
                      <TableHead>{t("common.price")}</TableHead>
                      <TableHead>{t("dashboard.change")}</TableHead>
                      <TableHead></TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Array.from({ length: 5 }).map((_, i) => (
                      <TableRow key={i}>
                        <TableCell colSpan={6}>
                          <Skeleton className="h-8 w-full" />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : topChanges.length === 0 ? (
                <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                  {t("dashboard.noData")}
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("dashboard.product")}</TableHead>
                      <TableHead>{t("dashboard.competitor")}</TableHead>
                      <TableHead>{t("common.price")}</TableHead>
                      <TableHead>{t("dashboard.change")}</TableHead>
                      <TableHead></TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {topChanges.map((row, i) => {
                      const isDrop = row.change_percent < 0;
                      const marketplace = competitorNameToMarketplace(row.competitor_name);
                      return (
                        <TableRow
                          key={i}
                          className={cn(
                            isDrop
                              ? "bg-price-down/5 dark:bg-price-down/10"
                              : "bg-price-up/5 dark:bg-price-up/10"
                          )}
                        >
                          <TableCell className="font-medium">{row.product_name}</TableCell>
                          <TableCell>{row.competitor_name}</TableCell>
                          <TableCell>
                            <PriceChangeCell
                              oldPrice={Number(row.old_price)}
                              newPrice={Number(row.new_price)}
                            />
                          </TableCell>
                          <TableCell>
                            <span
                              className={cn(
                                "font-medium",
                                isDrop
                                  ? "text-price-down dark:text-price-down"
                                  : "text-price-up dark:text-price-up"
                              )}
                            >
                              {row.change_percent > 0 ? "+" : ""}
                              {row.change_percent.toFixed(1)}%
                            </span>
                          </TableCell>
                          <TableCell>
                            <MarketplaceBadge marketplace={marketplace} size="sm" />
                          </TableCell>
                          <TableCell>
                            <TrendBadge
                              trend={isDrop ? "down" : "up"}
                              value={Math.abs(row.change_percent)}
                              size="sm"
                            />
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Two-column grid: active promos + anomalies */}
      <section className="grid grid-cols-1 gap-4 animate-in fade-in-0 slide-in-from-bottom-2 fill-mode-both delay-200 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>{t("dashboard.activePromos")}</CardTitle>
            <Link
              to="/alerts"
              className="text-sm font-medium text-primary underline-offset-4 hover:underline dark:text-primary"
            >
              {t("dashboard.showAll")}
            </Link>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : activePromos.length === 0 ? (
              <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                {t("dashboard.noData")}
              </p>
            ) : (
              <div className="space-y-2">
                {activePromos.map((p, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between gap-2 rounded-md border border-border bg-muted/30 p-2 dark:border-border dark:bg-muted/20"
                  >
                    <PromoBadge type="promo" label={p.promo_label} />
                    <span className="truncate text-sm font-medium">{p.product_name}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-promo/50 dark:border-promo/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="size-5 text-promo dark:text-promo" />
              {t("dashboard.anomalies")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {anomaliesLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 2 }).map((_, i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : anomalies.length === 0 ? (
              <EmptyState
                title="dashboard.anomaliesEmpty"
                description="dashboard.noData"
              />
            ) : (
              <ul className="space-y-2">
                {anomalies.map((a, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between gap-2 rounded-md border border-border bg-muted/30 p-2 dark:border-border dark:bg-muted/20"
                  >
                    <span className="truncate text-sm">{a.product_name}</span>
                    <span className="shrink-0 rounded-md border border-price-up/30 bg-price-up/15 px-2 py-0.5 text-xs font-medium text-price-up dark:border-price-up/40 dark:bg-price-up/20 dark:text-price-up">
                      {a.change_percent > 0 ? "+" : ""}
                      {a.change_percent.toFixed(1)}%
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
