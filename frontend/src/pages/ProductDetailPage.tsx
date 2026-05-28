// MOBILE-2026: fully responsive + bottom nav + drawer

/**
 * Product detail page: header, tabs (Chart | Competitors | Alerts).
 * Data from useProduct, analyticsApi.getPriceHistory, analyticsApi.getComparison, useAlerts.
 */

import { useState, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LineChart,
  Line,
  Area,
  AreaChart,
  ReferenceArea,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  type TooltipProps,
} from "recharts";
import {
  ArrowLeft,
  RefreshCw,
  ExternalLink,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { formatPrice, formatDate, formatRelativeTime, formatChartDate } from "@/lib/formatters";
import { CHART_COLORS, CHART_PRIMARY } from "@/lib/design-tokens";
import { analyticsApi } from "@/api/analytics";
import { useProduct } from "@/hooks/useProducts";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TrendBadge } from "@/components/ui-custom/TrendBadge";
import { MarketplaceBadge } from "@/components/ui-custom/MarketplaceBadge";
import { PromoBadge } from "@/components/ui-custom/PromoBadge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type Period = "7d" | "30d" | "90d";

interface ChartDataPoint {
  date: string;
  dateLabel: string;
  myPrice: number;
  [key: string]: string | number | null;
}

export function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t, i18n } = useTranslation();
  const locale = i18n.language;

  const [period, setPeriod] = useState<Period>("7d");

  const { data: product, isLoading: productLoading } = useProduct(id);
  const { data: priceHistory, isLoading: historyLoading } = useQuery({
    queryKey: ["products", id, "price-history", period],
    queryFn: async () => {
      if (!id) return null;
      const { data } = await analyticsApi.getPriceHistory(id, period);
      return data;
    },
    enabled: !!id,
  });
  const { data: comparison } = useQuery({
    queryKey: ["products", id, "comparison"],
    queryFn: async () => {
      if (!id) return null;
      const { data } = await analyticsApi.getComparison(id);
      return data;
    },
    enabled: !!id,
  });
  const forecastData = useMemo(() => {
    const days = 14;
    const data: Array<{ date: string; dateLabel: string; forecast: number; low: number; high: number }> = [];
    const base = 120;
    const now = new Date();
    for (let i = 0; i < days; i++) {
      const d = new Date(now);
      d.setDate(d.getDate() + i);
      const dateStr = d.toISOString().slice(0, 10);
      const trend = i * 2;
      const noise = () => (Math.random() - 0.5) * 15;
      const f = Math.round(base + trend + noise());
      data.push({
        date: dateStr,
        dateLabel: formatChartDate(d, locale),
        forecast: f,
        low: Math.max(0, f - 20),
        high: f + 25,
      });
    }
    return data;
  }, [locale]);

  const chartData = useMemo((): ChartDataPoint[] => {
    if (!priceHistory || !product) return [];
    const myPrice = Number(priceHistory.my_price);
    const dateToPoint = new Map<string, ChartDataPoint>();

    priceHistory.competitors.forEach((comp) => {
      const name = String(comp.competitor_name ?? "").slice(0, 100);
      if (!name) return;
      comp.data_points.forEach((dp) => {
        const dateStr = typeof dp.date === "string" ? dp.date.slice(0, 10) : String(dp.date).slice(0, 10);
        let point = dateToPoint.get(dateStr);
        if (!point) {
          point = { date: dateStr, dateLabel: "", myPrice };
          dateToPoint.set(dateStr, point);
        }
        Object.defineProperty(point, name, { value: Number(dp.price), enumerable: true });
      });
    });

    const points = Array.from(dateToPoint.values()).sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    );
    return points.map((p) => ({
      ...p,
      dateLabel: formatDate(p.date, locale),
    }));
  }, [priceHistory, product, locale]);

  const competitorProducts = product?.competitor_products ?? [];
  const comparisonCompetitors = comparison?.competitors ?? [];
  const myPriceForCompare = product?.current_price ?? 0;
  const displayCompetitors = competitorProducts.length > 0
    ? competitorProducts.map((c) => {
        const diffPercent =
          c.last_price != null && myPriceForCompare > 0
            ? ((Number(c.last_price) - myPriceForCompare) / myPriceForCompare) * 100
            : null;
        const trend: "up" | "down" | "stable" =
          diffPercent == null
            ? "stable"
            : diffPercent > 1
              ? "up"
              : diffPercent < -1
                ? "down"
                : "stable";
        return {
          id: c.id,
          competitor_name: c.competitor_name,
          marketplace: c.marketplace ?? c.competitor_name,
          url: c.url,
          last_price: c.last_price,
          last_promo_label: c.last_promo_label,
          last_in_stock: c.last_in_stock,
          last_checked_at: c.last_checked_at,
          trend,
        };
      })
    : comparisonCompetitors.map((c, i) => ({
        id: `comp-${i}`,
        competitor_name: c.name,
        marketplace: c.name,
        url: "#",
        last_price: c.price,
        last_promo_label: c.promo_label,
        last_in_stock: c.in_stock,
        last_checked_at: null,
        trend: c.trend,
      }));
  const isParsed = competitorProducts.some((c) => c.last_checked_at) || comparisonCompetitors.length > 0;

  if (!id) {
    return (
      <div className="space-y-6">
        <Link to="/products" className={buttonVariants({ variant: "ghost", size: "icon" })}>
          <ArrowLeft className="size-5" />
        </Link>
        <p className="text-muted-foreground">{t("common.dash")}</p>
      </div>
    );
  }

  if (productLoading || !product) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const myPrice = product.current_price;

  // TODO: GET /api/products/{id}/ai-recommendation
  const minComp = displayCompetitors
    .map((c) => c.last_price)
    .filter((p): p is number => p != null)
    .reduce<number | null>((acc, p) => (acc == null ? p : Math.min(acc, p)), null);
  const aiRecType =
    minComp == null || minComp <= 0
      ? "keep"
      : ((myPrice - minComp) / minComp) * 100 > 8
        ? "lower"
        : ((myPrice - minComp) / minComp) * 100 < -5
          ? "raise"
          : "keep";
  const aiRecKey =
    aiRecType === "lower"
      ? "productDetail.aiRecommendationLower5"
      : aiRecType === "raise"
        ? "productDetail.aiRecommendationRaise"
        : "productDetail.aiRecommendationKeep";

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/products"
            className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "min-h-12 min-w-12 shrink-0 touch-manipulation")}
          >
            <ArrowLeft className="size-5" />
          </Link>
          <div className="min-w-0 flex flex-1 flex-wrap items-center gap-2">
            <h1 className="truncate font-display text-lg font-bold tracking-tight sm:text-xl md:text-2xl lg:text-3xl">
              {product.name}
            </h1>
            {product.sku && (
              <Badge variant="secondary" className="font-normal text-muted-foreground dark:text-muted-foreground">
                {product.sku}
              </Badge>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <p className="text-sm text-muted-foreground dark:text-muted-foreground">
              {t("productDetail.myPrice")}
            </p>
            <p className="text-2xl font-bold text-primary dark:text-primary">
              {formatPrice(myPrice, "RUB", locale)}
            </p>
          </div>
          <Badge
            variant="secondary"
            className={cn(
              "text-sm",
              aiRecType === "lower" &&
                "bg-price-down/15 text-price-down border-price-down/30 dark:bg-price-down/20 dark:text-price-down",
              aiRecType === "keep" &&
                "bg-muted text-muted-foreground border-border dark:bg-muted/80 dark:text-muted-foreground",
              aiRecType === "raise" &&
                "bg-primary/15 text-primary border-primary/30 dark:bg-primary/20 dark:text-primary"
            )}
          >
            {t(aiRecKey)}
          </Badge>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "size-3 rounded-full",
                isParsed ? "bg-price-down dark:bg-price-down" : "bg-muted dark:bg-muted"
              )}
              title={isParsed ? t("productDetail.parseSuccess") : t("productDetail.parsePending")}
            />
            <span className="text-sm text-muted-foreground dark:text-muted-foreground">
              {isParsed ? t("productDetail.parseSuccess") : t("productDetail.parsePending")}
            </span>
          </div>
          <Button variant="outline" size="sm">
            <RefreshCw className="mr-2 size-4" />
            {t("productDetail.runParsing")}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="chart">
        <TabsList className="w-full flex-wrap sm:w-auto">
          <TabsTrigger value="chart">{t("productDetail.priceDynamics")}</TabsTrigger>
          <TabsTrigger value="competitors">{t("productDetail.competitors")}</TabsTrigger>
          <TabsTrigger value="forecast">{t("productDetail.salesForecast")}</TabsTrigger>
        </TabsList>

        <TabsContent value="chart" className="mt-4 animate-in fade-in-0 duration-200">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {(["7d", "30d", "90d"] as const).map((p) => (
                <Button
                  key={p}
                  variant={period === p ? "default" : "outline"}
                  size="sm"
                  onClick={() => setPeriod(p)}
                >
                  {p === "7d" ? t("productDetail.period7d") : p === "30d" ? t("productDetail.period30d") : t("productDetail.period90d")}
                </Button>
              ))}
            </div>
            <div className="glass-card h-64 w-full min-w-0 rounded-xl p-4 sm:h-72 md:h-80">
              {historyLoading ? (
                <Skeleton className="h-full w-full" />
              ) : chartData.length === 0 ? (
                <div
                  className="flex h-full items-center justify-center rounded-lg"
                  style={{
                    border: "1px solid var(--glass-border)",
                    background: "var(--glass-bg)",
                  }}
                >
                  <p className="text-sm" style={{ color: "var(--foreground-muted)" }}>
                    {t("dashboard.noData")}
                  </p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="var(--border)"
                      strokeOpacity={0.5}
                    />
                    <XAxis
                      dataKey="dateLabel"
                      tick={{ fontSize: 12, fill: "var(--foreground-muted)" }}
                      stroke="var(--foreground-muted)"
                    />
                    <YAxis
                      tick={{ fontSize: 12, fill: "var(--foreground-muted)" }}
                      stroke="var(--foreground-muted)"
                      tickFormatter={(v) => formatPrice(v, "RUB", locale)}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="myPrice"
                      name={t("productDetail.myPriceLegend")}
                      stroke={CHART_PRIMARY}
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      dot={false}
                      connectNulls
                    />
                    {priceHistory?.competitors.map((comp, i) => (
                      <Line
                        key={comp.competitor_name}
                        type="monotone"
                        dataKey={comp.competitor_name}
                        name={comp.competitor_name}
                        stroke={CHART_COLORS[i % CHART_COLORS.length]}
                        strokeWidth={2}
                        dot={false}
                        connectNulls
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="forecast" className="mt-4 animate-in fade-in-0 duration-200">
          <div className="glass-card h-80 w-full rounded-xl p-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={forecastData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="forecastAreaGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--border)"
                  strokeOpacity={0.5}
                />
                <XAxis
                  dataKey="dateLabel"
                  tick={{ fontSize: 12, fill: "var(--foreground-muted)" }}
                  stroke="var(--foreground-muted)"
                />
                <YAxis
                  tick={{ fontSize: 12, fill: "var(--foreground-muted)" }}
                  stroke="var(--foreground-muted)"
                  tickFormatter={(v) => String(v)}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const p = payload[0]?.payload as (typeof forecastData)[0];
                    return (
                      <div
                        className="rounded-md px-3 py-2 shadow-md"
                        style={{
                          background: "var(--background-elevated)",
                          border: "1px solid var(--glass-border)",
                          backdropFilter: "blur(16px)",
                        }}
                      >
                        <p className="mb-2 font-medium">{p?.dateLabel}</p>
                        <p className="text-sm">
                          {t("productDetail.forecastSales")}: {p?.forecast}
                        </p>
                        <p className="text-xs text-muted-foreground dark:text-muted-foreground">
                          {t("productDetail.confidenceInterval")}: {p?.low}–{p?.high}
                        </p>
                      </div>
                    );
                  }}
                />
                {forecastData.map((item, i) => (
                  <ReferenceArea
                    key={i}
                    x1={i - 0.5}
                    x2={i + 0.5}
                    y1={item?.low ?? 0}
                    y2={item?.high ?? 0}
                    fill="var(--accent)"
                    fillOpacity={0.15}
                  />
                ))}
                <Area
                  type="monotone"
                  dataKey="forecast"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  fill="url(#forecastAreaGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </TabsContent>

        <TabsContent value="competitors" className="mt-4 animate-in fade-in-0 duration-200">
          <div className="space-y-4">
            <div className="overflow-x-auto rounded-lg border border-border dark:border-border">
              {competitorProducts.length === 0 ? (
                <p className="p-4 text-sm text-muted-foreground dark:text-muted-foreground">
                  {t("dashboard.noData")}
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("dashboard.competitor")}</TableHead>
                      <TableHead>{t("competitors.marketplace")}</TableHead>
                      <TableHead>{t("common.price")}</TableHead>
                      <TableHead>{t("productDetail.diffPercent")}</TableHead>
                      <TableHead>{t("productDetail.promo")}</TableHead>
                      <TableHead>{t("productDetail.stock")}</TableHead>
                      <TableHead>{t("competitors.tableLastChecked")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {displayCompetitors.map((c) => {
                      const price = c.last_price;
                      const diffPercent =
                        price != null && myPrice > 0
                          ? ((Number(price) - myPrice) / myPrice) * 100
                          : null;
                      const marketplace = c.marketplace ?? c.competitor_name;

                      return (
                        <TableRow key={c.id}>
                          <TableCell>
                            <a
                              href={c.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 font-medium text-primary hover:underline dark:text-primary"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {c.competitor_name}
                              <ExternalLink className="size-4" />
                            </a>
                          </TableCell>
                          <TableCell>
                            <MarketplaceBadge marketplace={marketplace} size="sm" />
                          </TableCell>
                          <TableCell>
                            {price != null ? formatPrice(Number(price), "RUB", locale) : t("common.dash")}
                          </TableCell>
                          <TableCell>
                            {diffPercent != null ? (
                              <TrendBadge
                                trend={c.trend}
                                value={Math.abs(diffPercent)}
                                size="sm"
                              />
                            ) : (
                              t("common.dash")
                            )}
                          </TableCell>
                          <TableCell>
                            {c.last_promo_label ? (
                              <PromoBadge type="promo" label={c.last_promo_label} className="text-xs" />
                            ) : (
                              t("common.dash")
                            )}
                          </TableCell>
                          <TableCell>
                            <span
                              className={cn(
                                "size-2 rounded-full",
                                c.last_in_stock === true ? "bg-price-down dark:bg-price-down" : "bg-muted dark:bg-muted"
                              )}
                            />
                            {c.last_in_stock === true
                              ? t("productDetail.inStock")
                              : c.last_in_stock === false
                                ? t("productDetail.outOfStock")
                                : t("common.dash")}
                          </TableCell>
                          <TableCell className="text-muted-foreground dark:text-muted-foreground">
                            {c.last_checked_at
                              ? formatRelativeTime(c.last_checked_at, locale)
                              : t("common.dash")}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ChartTooltip(props: TooltipProps<number, string>) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const { active, payload, label } = props;
  if (!active || !payload?.length) return null;
  const item = payload[0]?.payload as ChartDataPoint;
  return (
    <div
      className="rounded-md px-3 py-2 shadow-md"
      style={{
        background: "var(--background-elevated)",
        border: "1px solid var(--glass-border)",
        backdropFilter: "blur(16px)",
      }}
    >
      <p className="mb-2 font-medium">{item ? formatDate(item.date, locale) : label}</p>
      <div className="space-y-1 text-sm">
        <p>
          {t("productDetail.myPriceLegend")}: {item?.myPrice != null ? formatPrice(item.myPrice, "RUB", locale) : t("common.dash")}
        </p>
        {payload.map((p) => {
          if (p.dataKey === "myPrice") return null;
          return (
            <p key={String(p.dataKey)}>
              {p.name}: {p.value != null ? formatPrice(p.value as number, "RUB", locale) : t("common.dash")}
            </p>
          );
        })}
      </div>
    </div>
  );
}

