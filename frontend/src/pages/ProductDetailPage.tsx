/**
 * Product detail page: header, tabs (Chart | Competitors | Alerts).
 *
 * i18n keys used:
 * - common.back, common.dash
 * - products.sku, products.myPrice
 * - productDetail.priceChart, productDetail.competitors, productDetail.alerts
 * - productDetail.myPrice, productDetail.myPriceLegend
 * - productDetail.period7d, productDetail.period30d, productDetail.period90d
 * - productDetail.runParsing, productDetail.parseSuccess, productDetail.parsePending
 * - productDetail.diffPercent, productDetail.promo, productDetail.inStock, productDetail.outOfStock
 * - productDetail.createAlert
 * - competitors.addCompetitor
 * - alerts.noAlerts, alerts.typePriceDrop, alerts.typePriceIncrease, alerts.typeOutOfStock, alerts.typeNewPromo
 * - alerts.threshold, alerts.channelEmail, alerts.channelTelegram
 * - competitors.marketplaceOzon, competitors.marketplaceWb, competitors.marketplaceKaspi
 * - ui.promo
 */

import { useState, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
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
import { formatPrice, formatDate, formatRelativeTime } from "@/lib/formatters";
import { CHART_COLORS, CHART_PRIMARY } from "@/lib/design-tokens";
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

interface CompetitorRow {
  id: string;
  name: string;
  url: string;
  marketplace: Marketplace;
  price: number | null;
  diffPercent: number | null;
  promoLabel: string | null;
  inStock: boolean | null;
  lastCheckedAt: string | null;
}

interface AlertRow {
  id: string;
  type: AlertType;
  threshold: number;
  channel: AlertChannel;
  enabled: boolean;
}

// TODO: API — replace with useProduct(id), usePriceHistory(id, period), useComparison(id)
const MOCK_PRODUCT = {
  id: "1",
  name: "Смартфон Galaxy A55 128GB",
  sku: "GAL-A55-128",
  current_price: 32490,
  lastParsedAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
};

const MOCK_CHART_DATA_7D: ChartDataPoint[] = (() => {
  const points: ChartDataPoint[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);
    points.push({
      date: dateStr,
      dateLabel: "",
      myPrice: 32000 + i * 100,
      Ozon: 28990 + i * 80,
      Wildberries: 29500 + i * 50,
      "Ozon_promo": i === 3 ? "Скидка 10%" : null,
    });
  }
  return points;
})();

const MOCK_COMPETITORS: CompetitorRow[] = [
  { id: "1", name: "Ozon", url: "https://ozon.ru/...", marketplace: "ozon", price: 28990, diffPercent: -10.8, promoLabel: "Скидка 10%", inStock: true, lastCheckedAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString() },
  { id: "2", name: "Wildberries", url: "https://wb.ru/...", marketplace: "wildberries", price: 31500, diffPercent: -3.1, promoLabel: null, inStock: true, lastCheckedAt: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString() },
  { id: "3", name: "Kaspi", url: "https://kaspi.kz/...", marketplace: "kaspi", price: 29990, diffPercent: -7.7, promoLabel: null, inStock: false, lastCheckedAt: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString() },
];

const MOCK_ALERTS: AlertRow[] = [
  { id: "1", type: "price_drop", threshold: 10, channel: "email", enabled: true },
  { id: "2", type: "price_increase", threshold: 5, channel: "telegram", enabled: false },
];

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
  const { t, i18n } = useTranslation();
  const locale = i18n.language;

  const [period, setPeriod] = useState<Period>("7d");
  const [visibleSeries, setVisibleSeries] = useState<Record<string, boolean>>({
    myPrice: true,
    Ozon: true,
    Wildberries: true,
  });

  const product = MOCK_PRODUCT;
  const isParsed = !!product.lastParsedAt;

  const chartData = useMemo(() => {
    const data = [...MOCK_CHART_DATA_7D];
    return data.map((p) => ({
      ...p,
      dateLabel: formatDate(p.date, locale),
    }));
  }, [locale]);

  const competitors = ["myPrice", "Ozon", "Wildberries"].filter(
    (k) => k === "myPrice" || visibleSeries[k] !== false
  );

  const toggleSeries = (key: string) => {
    setVisibleSeries((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
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
              {formatPrice(product.current_price, "RUB", locale)}
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

      {/* Tabs */}
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
                  {visibleSeries.myPrice !== false && (
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
                  )}
                  {["Ozon", "Wildberries"].map((name, i) =>
                    visibleSeries[name] !== false ? (
                      <Line
                        key={name}
                        type="monotone"
                        dataKey={name}
                        name={name}
                        stroke={CHART_COLORS[i % CHART_COLORS.length]}
                        strokeWidth={2}
                        dot={false}
                        connectNulls
                      />
                    ) : null
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="flex overflow-x-auto gap-4 pb-2 sm:flex-wrap">
              {["myPrice", "Ozon", "Wildberries"].map((key, i) => (
                <label
                  key={key}
                  className="flex cursor-pointer items-center gap-2 shrink-0"
                >
                  <input
                    type="checkbox"
                    checked={visibleSeries[key] !== false}
                    onChange={() => toggleSeries(key)}
                    className="rounded border-input"
                  />
                  <span
                    className="h-1 w-4 shrink-0 rounded"
                    style={{
                      backgroundColor: key === "myPrice" ? CHART_PRIMARY : CHART_COLORS[i - 1],
                      border: key === "myPrice" ? "none" : undefined,
                    }}
                  />
                  <span className="text-sm">
                    {key === "myPrice" ? t("productDetail.myPriceLegend") : key}
                  </span>
                </label>
              ))}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="competitors" className="mt-4 animate-in fade-in-0 duration-200">
          <div className="space-y-4">
            <Button variant="outline" size="sm">
              <Plus className="mr-2 size-4" />
              {t("competitors.addCompetitor")}
            </Button>
            <div className="overflow-x-auto rounded-lg border border-border dark:border-border">
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
                  {MOCK_COMPETITORS.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell>
                        <a
                          href={c.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 font-medium text-primary hover:underline dark:text-primary"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {c.name}
                          <ExternalLink className="size-4" />
                        </a>
                      </TableCell>
                      <TableCell>
                        <MarketplaceBadge marketplace={c.marketplace} size="sm" />
                      </TableCell>
                      <TableCell>
                        {c.price != null ? formatPrice(c.price, "RUB", locale) : t("common.dash")}
                      </TableCell>
                      <TableCell>
                        {c.diffPercent != null ? (
                          <TrendBadge
                            trend={c.diffPercent > 0 ? "up" : c.diffPercent < 0 ? "down" : "stable"}
                            value={Math.abs(c.diffPercent)}
                            size="sm"
                          />
                        ) : (
                          t("common.dash")
                        )}
                      </TableCell>
                      <TableCell>
                        {c.promoLabel ? (
                          <PromoBadge type="promo" className="text-xs" />
                        ) : (
                          t("common.dash")
                        )}
                      </TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            "size-2 rounded-full",
                            c.inStock === true ? "bg-price-down dark:bg-price-down" : "bg-muted dark:bg-muted"
                          )}
                        />
                        {c.inStock === true
                          ? t("productDetail.inStock")
                          : c.inStock === false
                            ? t("productDetail.outOfStock")
                            : t("common.dash")}
                      </TableCell>
                      <TableCell className="text-muted-foreground dark:text-muted-foreground">
                        {c.lastCheckedAt
                          ? formatRelativeTime(c.lastCheckedAt, locale)
                          : t("common.dash")}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="alerts" className="mt-4 animate-in fade-in-0 duration-200">
          <div className="space-y-4">
            <div className="flex justify-end">
              <Button size="sm">
                <Plus className="mr-2 size-4" />
                {t("productDetail.createAlert")}
              </Button>
            </div>
            {MOCK_ALERTS.length === 0 ? (
              <EmptyState
                title="alerts.noAlerts"
                description="alerts.noAlertsHint"
                icon={Bell}
              />
            ) : (
              <div className="space-y-3">
                {MOCK_ALERTS.map((a) => (
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
  const item = payload[0]?.payload as ChartDataPoint & { Ozon_promo?: string | null };
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 shadow-md dark:border-border dark:bg-card">
      <p className="mb-2 font-medium">{item ? formatDate(item.date, locale) : label}</p>
      <div className="space-y-1 text-sm">
        <p>
          {t("productDetail.myPriceLegend")}: {item?.myPrice != null ? formatPrice(item.myPrice, "RUB", locale) : t("common.dash")}
        </p>
        {payload.map((p) => {
          if (p.dataKey === "myPrice") return null;
          const promo = item?.[`${String(p.dataKey)}_promo`];
          return (
            <p key={String(p.dataKey)} className="flex items-center gap-2">
              <span>
                {p.name}: {p.value != null ? formatPrice(p.value as number, "RUB", locale) : t("common.dash")}
              </span>
              {promo && <PromoBadge type="promo" />}
            </p>
          );
        })}
      </div>
    </div>
  );
}

function AlertItem({ alert }: { alert: AlertRow }) {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useState(alert.enabled);
  const Icon = CHANNEL_ICONS[alert.channel];
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-card p-4 dark:border-border dark:bg-card">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{t(ALERT_TYPE_KEYS[alert.type])}</Badge>
        <span className="text-sm text-muted-foreground dark:text-muted-foreground">
          {t("alerts.threshold")}: {alert.threshold}%
        </span>
        <Icon className="size-4 text-muted-foreground dark:text-muted-foreground" />
        <span className="text-sm">{t(CHANNEL_KEYS[alert.channel])}</span>
      </div>
      <Switch checked={enabled} onCheckedChange={setEnabled} />
    </div>
  );
}
