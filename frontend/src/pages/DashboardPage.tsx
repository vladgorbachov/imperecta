/**
 * Dashboard page with stats, top changes table, active promos, anomalies, weekly chart.
 *
 * i18n keys used:
 * - nav.dashboard
 * - dashboard.products, dashboard.competitors, dashboard.alertsToday, dashboard.priceChanges
 * - dashboard.topChangesToday, dashboard.updatedAgo, dashboard.showAll
 * - dashboard.activePromos, dashboard.anomalies, dashboard.anomaliesEmpty
 * - dashboard.weeklyChart, dashboard.product, dashboard.competitor
 * - dashboard.change, dashboard.noData
 * - ui.trendPercentPositive, ui.trendPercentNegative, ui.trendPercentZero
 * - ui.priceChangeArrow
 * - competitors.marketplaceOzon, competitors.marketplaceWb, competitors.marketplaceKaspi, competitors.marketplaceCustom
 * - ui.promo, ui.discount
 * - common.dash
 * - productDetail.myPriceLegend
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Package, Users, Bell, RefreshCw, AlertTriangle } from "lucide-react";
import { formatChartDate, formatPrice, formatRelativeTime } from "@/lib/formatters";
import { CHART_COLORS } from "@/lib/design-tokens";
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

type Marketplace = "ozon" | "wildberries" | "kaspi" | "custom";

interface TopChangeRow {
  product_name: string;
  competitor_name: string;
  old_price: number;
  new_price: number;
  change_percent: number;
  marketplace: Marketplace;
}

interface ActivePromoRow {
  product_name: string;
  competitor_name: string;
  promo_type: "promo" | "discount";
  discount_percent?: number;
}

interface AnomalyRow {
  product_name: string;
  change_percent: number;
}

interface WeeklyChartPoint {
  date: string;
  dateLabel: string;
  price: number;
}

// TODO: API — replace with useDashboardSummary / analyticsApi.getDashboardSummary()
const MOCK_STATS = {
  products: 128,
  competitors: 45,
  competitorsTrend: 3,
  alertsToday: 7,
  priceChangesTotal: 23,
  priceChangesUp: 12,
  priceChangesDown: 11,
};

const MOCK_LAST_UPDATED = new Date(Date.now() - 2 * 60 * 60 * 1000);

// TODO: API — replace with top_changes from dashboard summary
const MOCK_TOP_CHANGES: TopChangeRow[] = [
  {
    product_name: "Смартфон Galaxy A55",
    competitor_name: "Ozon",
    old_price: 32490,
    new_price: 28990,
    change_percent: -10.8,
    marketplace: "ozon",
  },
  {
    product_name: "Наушники Sony WH-1000XM5",
    competitor_name: "Wildberries",
    old_price: 28900,
    new_price: 31500,
    change_percent: 9.0,
    marketplace: "wildberries",
  },
  {
    product_name: "Пылесос Dyson V15",
    competitor_name: "Kaspi",
    old_price: 89990,
    new_price: 79990,
    change_percent: -11.1,
    marketplace: "kaspi",
  },
  {
    product_name: "Кофемашина DeLonghi",
    competitor_name: "Ozon",
    old_price: 45900,
    new_price: 42900,
    change_percent: -6.5,
    marketplace: "ozon",
  },
  {
    product_name: "Умные часы Apple Watch",
    competitor_name: "Wildberries",
    old_price: 32990,
    new_price: 35990,
    change_percent: 9.1,
    marketplace: "wildberries",
  },
];

// TODO: API — replace with active_promos from dashboard summary
const MOCK_ACTIVE_PROMOS: ActivePromoRow[] = [
  { product_name: "Смартфон Galaxy A55", competitor_name: "Ozon", promo_type: "discount", discount_percent: 15 },
  { product_name: "Пылесос Dyson V15", competitor_name: "Kaspi", promo_type: "promo" },
  { product_name: "Кофемашина DeLonghi", competitor_name: "Ozon", promo_type: "discount", discount_percent: 10 },
];

// TODO: API — replace with anomalies endpoint
const MOCK_ANOMALIES: AnomalyRow[] = [
  { product_name: "Наушники Sony WH-1000XM5", change_percent: 18.2 },
  { product_name: "Умные часы Apple Watch", change_percent: 9.1 },
];

// TODO: API — replace with weekly price history
const MOCK_WEEKLY_DATA: WeeklyChartPoint[] = (() => {
  const points: WeeklyChartPoint[] = [];
  const now = new Date();
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);
    points.push({
      date: dateStr,
      dateLabel: "",
      price: 32000 + Math.sin(i) * 2000 + i * 500,
    });
  }
  return points;
})();

export function DashboardPage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoading] = useState(false);

  // TODO: API — use useDashboardSummary() and wire isLoading, refetch
  // const { data, isLoading, refetch } = useDashboardSummary();

  const handleRefresh = async () => {
    setIsRefreshing(true);
    // TODO: API — await refetch()
    await new Promise((r) => setTimeout(r, 800));
    setIsRefreshing(false);
  };

  const updatedTime = formatRelativeTime(MOCK_LAST_UPDATED, locale);

  const chartData = MOCK_WEEKLY_DATA.map((p) => ({
    ...p,
    dateLabel: formatChartDate(p.date, locale),
  }));

  return (
    <div className="space-y-6">
      <PageHeader title="nav.dashboard" />

      {/* Section 1: Stats row */}
      <section
        className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4"
      >
        <StatCard
          title="dashboard.products"
          value={MOCK_STATS.products}
          icon={Package}
          isLoading={isLoading}
          className="animate-in fade-in-0 slide-in-from-bottom-2 fill-mode-both"
          style={{ animationDelay: "0ms" }}
        />
        <StatCard
          title="dashboard.competitors"
          value={MOCK_STATS.competitors}
          trend={{ direction: "up", value: MOCK_STATS.competitorsTrend }}
          icon={Users}
          isLoading={isLoading}
          className="animate-in fade-in-0 slide-in-from-bottom-2 fill-mode-both"
          style={{ animationDelay: "100ms" }}
        />
        <StatCard
          title="dashboard.alertsToday"
          value={MOCK_STATS.alertsToday}
          trend={{ direction: "up" }}
          icon={Bell}
          isLoading={isLoading}
          className="animate-in fade-in-0 slide-in-from-bottom-2 fill-mode-both"
          style={{ animationDelay: "200ms" }}
        />
        <StatCard
          title="dashboard.priceChanges"
          value={MOCK_STATS.priceChangesTotal}
          trendBadges={[
            { direction: "up", value: MOCK_STATS.priceChangesUp },
            { direction: "down", value: MOCK_STATS.priceChangesDown },
          ]}
          isLoading={isLoading}
          className="animate-in fade-in-0 slide-in-from-bottom-2 fill-mode-both"
          style={{ animationDelay: "300ms" }}
        />
      </section>

      {/* Section 2: Top 5 changes */}
      <section
        className="animate-in fade-in-0 slide-in-from-bottom-2 fill-mode-both delay-100"
      >
        <Card>
          <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle>{t("dashboard.topChangesToday")}</CardTitle>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground dark:text-muted-foreground">
                {t("dashboard.updatedAgo", { time: updatedTime })}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleRefresh}
                disabled={isRefreshing}
                aria-label={t("common.refresh")}
              >
                <RefreshCw
                  className={cn("size-4", isRefreshing && "animate-spin")}
                />
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
            ) : !MOCK_TOP_CHANGES.length ? (
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
                  {MOCK_TOP_CHANGES.map((row, i) => {
                    const isDrop = row.change_percent < 0;
                    return (
                      <TableRow
                        key={i}
                        className={cn(
                          isDrop
                            ? "bg-price-down/5 dark:bg-price-down/10"
                            : "bg-price-up/5 dark:bg-price-up/10"
                        )}
                      >
                        <TableCell className="font-medium">
                          {row.product_name}
                        </TableCell>
                        <TableCell>{row.competitor_name}</TableCell>
                        <TableCell>
                          <PriceChangeCell
                            oldPrice={row.old_price}
                            newPrice={row.new_price}
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
                          <MarketplaceBadge marketplace={row.marketplace} size="sm" />
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

      {/* Section 3: Two-column grid */}
      <section
        className="grid grid-cols-1 gap-4 animate-in fade-in-0 slide-in-from-bottom-2 fill-mode-both delay-200 lg:grid-cols-2"
      >
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
            ) : !MOCK_ACTIVE_PROMOS.length ? (
              <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                {t("dashboard.noData")}
              </p>
            ) : (
              <div className="space-y-2">
                {MOCK_ACTIVE_PROMOS.map((p, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between gap-2 rounded-md border border-border bg-muted/30 p-2 dark:border-border dark:bg-muted/20"
                  >
                    <PromoBadge
                      type={p.promo_type}
                      label={p.discount_percent?.toString()}
                    />
                    <span className="truncate text-sm font-medium">
                      {p.product_name}
                    </span>
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
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 2 }).map((_, i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : !MOCK_ANOMALIES.length ? (
              <EmptyState
                title="dashboard.anomaliesEmpty"
                description="dashboard.noData"
              />
            ) : (
              <ul className="space-y-2">
                {MOCK_ANOMALIES.map((a, i) => (
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

      {/* Section 4: Weekly chart */}
      <section
        className="animate-in fade-in-0 slide-in-from-bottom-2 fill-mode-both delay-300"
      >
        <Card>
          <CardHeader>
            <CardTitle>{t("dashboard.weeklyChart")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={chartData}
                  margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                >
                  <defs>
                    <linearGradient
                      id="areaGradient"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="0%"
                        stopColor={CHART_COLORS[0]}
                        stopOpacity={0.3}
                      />
                      <stop
                        offset="100%"
                        stopColor={CHART_COLORS[0]}
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    className="stroke-muted dark:stroke-muted"
                  />
                  <XAxis
                    dataKey="dateLabel"
                    tick={{ fontSize: 12 }}
                    stroke="hsl(var(--muted-foreground))"
                  />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    stroke="hsl(var(--muted-foreground))"
                    tickFormatter={(v) => formatPrice(v, "RUB", locale)}
                  />
                  <Tooltip
                    content={({ active, payload, label }) => {
                      if (!active || !payload?.length || !label) return null;
                      const item = payload[0]?.payload as WeeklyChartPoint;
                      return (
                        <div className="rounded-md border border-border bg-card px-3 py-2 shadow-md dark:border-border dark:bg-card">
                          <p className="text-sm font-medium">
                            {item ? formatChartDate(item.date, locale) : label}
                          </p>
                          <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                            {item?.price != null
                              ? formatPrice(item.price, "RUB", locale)
                              : t("common.dash")}
                          </p>
                        </div>
                      );
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="price"
                    name={t("productDetail.myPriceLegend")}
                    stroke={CHART_COLORS[0]}
                    fill="url(#areaGradient)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
