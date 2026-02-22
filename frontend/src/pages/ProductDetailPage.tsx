import { useState } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Plus } from "lucide-react";
import { useProduct } from "@/hooks/useProducts";
import { usePriceHistory, useComparison } from "@/hooks/useAnalytics";
import { PriceChart } from "@/components/charts/PriceChart";
import { Button } from "@/components/ui/button";
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
import { Skeleton } from "@/components/ui/skeleton";

type Period = "7d" | "30d" | "90d";

export function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useTranslation();
  const [period, setPeriod] = useState<Period>("7d");

  const { data: product, isLoading: productLoading } = useProduct(id);
  const { data: priceHistory, isLoading: historyLoading } = usePriceHistory(
    id,
    period
  );
  const { data: comparison, isLoading: comparisonLoading } = useComparison(id);

  if (productLoading || !product) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{product.name}</h1>
        <p className="text-muted-foreground">
          {product.sku && `${t("products.sku")}: ${product.sku} · `}
          {t("productDetail.myPrice")}: {Number(product.current_price).toFixed(2)} ₽
        </p>
      </div>

      <Tabs defaultValue="chart">
        <TabsList>
          <TabsTrigger value="chart">{t("productDetail.priceChart")}</TabsTrigger>
          <TabsTrigger value="competitors">{t("productDetail.competitors")}</TabsTrigger>
          <TabsTrigger value="alerts">{t("productDetail.alerts")}</TabsTrigger>
        </TabsList>

        <TabsContent value="chart" className="space-y-4">
          <div className="flex gap-2">
            {(["7d", "30d", "90d"] as const).map((p) => (
              <Button
                key={p}
                variant={period === p ? "default" : "outline"}
                size="sm"
                onClick={() => setPeriod(p)}
              >
                {p === "7d"
                  ? t("productDetail.period7d")
                  : p === "30d"
                    ? t("productDetail.period30d")
                    : t("productDetail.period90d")}
              </Button>
            ))}
          </div>
          <PriceChart data={priceHistory ?? undefined} isLoading={historyLoading} />
        </TabsContent>

        <TabsContent value="competitors">
          {comparisonLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : !comparison?.competitors?.length ? (
            <p className="text-muted-foreground">{t("dashboard.noData")}</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("dashboard.competitor")}</TableHead>
                  <TableHead>{t("products.myPrice")}</TableHead>
                  <TableHead>Diff %</TableHead>
                  <TableHead>Promo</TableHead>
                  <TableHead>Stock</TableHead>
                  <TableHead>Trend</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {comparison.competitors.map((c, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{c.name}</TableCell>
                    <TableCell>
                      {c.price != null ? `${Number(c.price).toFixed(2)} ₽` : "—"}
                    </TableCell>
                    <TableCell>
                      {c.diff_percent != null ? (
                        <span
                          className={
                            c.diff_percent < 0
                              ? "text-green-600"
                              : c.diff_percent > 0
                                ? "text-red-600"
                                : ""
                          }
                        >
                          {c.diff_percent > 0 ? "+" : ""}
                          {c.diff_percent.toFixed(1)}%
                        </span>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell>
                      {c.promo_label ? (
                        <Badge variant="secondary">{c.promo_label}</Badge>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell>
                      {c.in_stock === true
                        ? t("productDetail.inStock")
                        : c.in_stock === false
                          ? t("productDetail.outOfStock")
                          : "—"}
                    </TableCell>
                    <TableCell>
                      <TrendBadge trend={c.trend} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>

        <TabsContent value="alerts">
          <div className="flex items-center justify-between">
            <p className="text-muted-foreground">{t("dashboard.noData")}</p>
            <Button>
              <Plus className="mr-2 size-4" />
              {t("productDetail.createAlert")}
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function TrendBadge({ trend }: { trend: "up" | "down" | "stable" }) {
  const { t } = useTranslation();
  const config = {
    up: {
      label: t("productDetail.trendUp"),
      className: "bg-red-100 text-red-800 hover:bg-red-100",
    },
    down: {
      label: t("productDetail.trendDown"),
      className: "bg-green-100 text-green-800 hover:bg-green-100",
    },
    stable: {
      label: t("productDetail.trendStable"),
      className: "",
    },
  };
  const { label, className } = config[trend];
  return (
    <Badge variant="secondary" className={className}>
      {label}
    </Badge>
  );
}
