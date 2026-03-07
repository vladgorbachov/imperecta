/**
 * Product detail page: header, tabs (Chart | Competitors | Alerts).
 * Data from useProduct, analyticsApi.getPriceHistory, analyticsApi.getComparison, useAlerts.
 */

import { useState, useMemo } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LineChart,
  Line,
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
  Plus,
  ExternalLink,
  Bell,
  Mail,
  Send,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { formatPrice, formatDate, formatRelativeTime } from "@/lib/formatters";
import { CHART_COLORS, CHART_PRIMARY } from "@/lib/design-tokens";
import { analyticsApi } from "@/api/analytics";
import { useProduct } from "@/hooks/useProducts";
import { useAlerts } from "@/hooks/useAlerts";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
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
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type Marketplace = "ozon" | "wildberries" | "kaspi" | "custom";
type Period = "7d" | "30d" | "90d";
type AlertType = "price_drop" | "price_increase" | "out_of_stock" | "new_promo";
type AlertChannel = "email" | "telegram";

interface ChartDataPoint {
  date: string;
  dateLabel: string;
  myPrice: number;
  [key: string]: string | number | null;
}

function competitorNameToMarketplace(name: string): Marketplace {
  const lower = name.toLowerCase();
  if (lower.includes("ozon")) return "ozon";
  if (lower.includes("wildberries") || lower.includes("wb")) return "wildberries";
  if (lower.includes("kaspi")) return "kaspi";
  return "custom";
}

const ALERT_TYPE_KEYS: Record<AlertType, string> = {
  price_drop: "alerts.typePriceDrop",
  price_increase: "alerts.typePriceIncrease",
  out_of_stock: "alerts.typeOutOfStock",
  new_promo: "alerts.typeNewPromo",
};

const CHANNEL_ICONS: Record<AlertChannel, typeof Mail> = {
  email: Mail,
  telegram: Send,
};

const CHANNEL_KEYS: Record<AlertChannel, string> = {
  email: "alerts.channelEmail",
  telegram: "alerts.channelTelegram",
};

export function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
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
  const { alerts = [] } = useAlerts();

  const productAlerts = useMemo(
    () => alerts.filter((a) => a.product_id === id || !a.product_id),
    [alerts, id]
  );

  const chartData = useMemo((): ChartDataPoint[] => {
    if (!priceHistory || !product) return [];
    const myPrice = Number(priceHistory.my_price);
    const dateToPoint: Record<string, ChartDataPoint> = {};

    priceHistory.competitors.forEach((comp, compIdx) => {
      comp.data_points.forEach((dp) => {
        const dateStr = typeof dp.date === "string" ? dp.date.slice(0, 10) : String(dp.date).slice(0, 10);
        if (!dateToPoint[dateStr]) {
          dateToPoint[dateStr] = {
            date: dateStr,
            dateLabel: "",
            myPrice,
          };
        }
        (dateToPoint[dateStr] as Record<string, unknown>)[comp.competitor_name] = Number(dp.price);
      });
    });

    const points = Object.values(dateToPoint).sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    );
    return points.map((p) => ({
      ...p,
      dateLabel: formatDate(p.date, locale),
    }));
  }, [priceHistory, product, locale]);

  const competitorProducts = product?.competitor_products ?? [];
  const comparisonCompetitors = comparison?.competitors ?? [];
  const displayCompetitors = competitorProducts.length > 0
    ? competitorProducts.map((c) => ({
        id: c.id,
        competitor_name: c.competitor_name,
        url: c.url,
        last_price: c.last_price,
        last_promo_label: c.last_promo_label,
        last_in_stock: c.last_in_stock,
        last_checked_at: c.last_checked_at,
      }))
    : comparisonCompetitors.map((c, i) => ({
        id: `comp-${i}`,
        competitor_name: c.name,
        url: "#",
        last_price: c.price,
        last_promo_label: c.promo_label,
        last_in_stock: c.in_stock,
        last_checked_at: null,
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

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/products"
            className={buttonVariants({ variant: "ghost", size: "icon" })}
          >
            <ArrowLeft className="size-5" />
          </Link>
          <div className="flex flex-1 flex-wrap items-center gap-2">
            <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">
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
        <TabsList className="w-full sm:w-auto">
          <TabsTrigger value="chart">{t("productDetail.priceChart")}</TabsTrigger>
          <TabsTrigger value="competitors">{t("productDetail.competitors")}</TabsTrigger>
          <TabsTrigger value="alerts">{t("productDetail.alerts")}</TabsTrigger>
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
            <div className="h-80 w-full">
              {historyLoading ? (
                <Skeleton className="h-full w-full" />
              ) : chartData.length === 0 ? (
                <div className="flex h-full items-center justify-center rounded-lg border border-border bg-muted/30 dark:border-border dark:bg-muted/20">
                  <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                    {t("dashboard.noData")}
                  </p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted dark:stroke-muted" />
                    <XAxis dataKey="dateLabel" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                    <YAxis
                      tick={{ fontSize: 12 }}
                      stroke="hsl(var(--muted-foreground))"
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

        <TabsContent value="competitors" className="mt-4 animate-in fade-in-0 duration-200">
          <div className="space-y-4">
            <Button variant="outline" size="sm" onClick={() => navigate("/competitors")}>
              <Plus className="mr-2 size-4" />
              {t("competitors.addCompetitor")}
            </Button>
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
                      const marketplace = competitorNameToMarketplace(c.competitor_name);

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
                                trend={diffPercent > 0 ? "up" : diffPercent < 0 ? "down" : "stable"}
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

        <TabsContent value="alerts" className="mt-4 animate-in fade-in-0 duration-200">
          <div className="space-y-4">
            <Button size="sm" onClick={() => navigate("/alerts")}>
              <Plus className="mr-2 size-4" />
              {t("productDetail.createAlert")}
            </Button>
            {productAlerts.length === 0 ? (
              <EmptyState
                title="alerts.noAlerts"
                description="alerts.noAlertsHint"
                icon={Bell}
              />
            ) : (
              <div className="space-y-3">
                {productAlerts.map((a) => (
                  <AlertItem key={a.id} alert={a} />
                ))}
              </div>
            )}
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
    <div className="rounded-md border border-border bg-card px-3 py-2 shadow-md dark:border-border dark:bg-card">
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

function AlertItem({ alert }: { alert: { id: string; type: string; threshold_percent: number | null; channel: string; is_active: boolean } }) {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useState(alert.is_active);
  const Icon = CHANNEL_ICONS[alert.channel as AlertChannel] ?? Mail;
  const typeKey = ALERT_TYPE_KEYS[alert.type as AlertType] ?? "alerts.typePriceDrop";
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-card p-4 dark:border-border dark:bg-card">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{t(typeKey)}</Badge>
        <span className="text-sm text-muted-foreground dark:text-muted-foreground">
          {t("alerts.threshold")}: {alert.threshold_percent ?? 0}%
        </span>
        <Icon className="size-4 text-muted-foreground dark:text-muted-foreground" />
        <span className="text-sm">{t(CHANNEL_KEYS[alert.channel as AlertChannel] ?? "alerts.channelEmail")}</span>
      </div>
      <Switch checked={enabled} onCheckedChange={setEnabled} />
    </div>
  );
}
