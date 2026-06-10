// MOBILE-2026: fully responsive + bottom nav + drawer

/**
 * Product detail page: header (price, AI recommendation, parse state) and
 * a Competitors section fed by `useProduct().competitor_products`. Price
 * chart and forecast were removed in A1: their data sources violated
 * Rule 3 (hardcoded stubs and client-side fabricated random numbers).
 * A real price-chart will return once `fact_price` is populated.
 */

import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, RefreshCw, ExternalLink } from "lucide-react";
import { PriceDisplay } from "@/components/ui-custom/PriceDisplay";
import { formatRelativeTime } from "@/lib/formatters";
import { useProduct } from "@/hooks/useProducts";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Badge } from "@/components/ui/badge";
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

type CompetitorTrend = "up" | "down" | "stable";

function diffTrend(diffPercent: number | null): CompetitorTrend {
  if (diffPercent == null) return "stable";
  if (diffPercent > 1) return "up";
  if (diffPercent < -1) return "down";
  return "stable";
}

export function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t, i18n } = useTranslation();
  const locale = i18n.language;

  const { data: product, isLoading: productLoading } = useProduct(id);

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
  const competitorProducts = product.competitor_products ?? [];
  const isParsed = competitorProducts.some((c) => c.last_checked_at);

  const displayCompetitors = competitorProducts.map((c) => {
    const diffPercent =
      c.last_price != null && myPrice > 0
        ? ((Number(c.last_price) - myPrice) / myPrice) * 100
        : null;
    return {
      id: c.id,
      competitor_name: c.competitor_name,
      marketplace: c.competitor_name,
      url: c.url,
      last_price: c.last_price,
      last_promo_label: c.last_promo_label,
      last_in_stock: c.last_in_stock,
      last_checked_at: c.last_checked_at,
      trend: diffTrend(diffPercent),
    };
  });

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
            className={cn(
              buttonVariants({ variant: "ghost", size: "icon" }),
              "min-h-12 min-w-12 shrink-0 touch-manipulation",
            )}
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
              <PriceDisplay localAmount={myPrice} localCurrency={product.currency} />
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
                "bg-primary/15 text-primary border-primary/30 dark:bg-primary/20 dark:text-primary",
            )}
          >
            {t(aiRecKey)}
          </Badge>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "size-3 rounded-full",
                isParsed ? "bg-price-down dark:bg-price-down" : "bg-muted dark:bg-muted",
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

      <section className="space-y-4">
        <h2 className="text-sm font-semibold text-muted-foreground dark:text-muted-foreground">
          {t("productDetail.competitors")}
        </h2>
        <div className="space-y-4">
          <div className="overflow-x-auto rounded-lg border border-border dark:border-border">
            {displayCompetitors.length === 0 ? (
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
                            <MarketplaceBadge marketplace={c.marketplace} size="sm" />
                          </TableCell>
                          <TableCell>
                            <PriceDisplay localAmount={price} localCurrency={product.currency} />
                          </TableCell>
                          <TableCell>
                            {diffPercent != null ? (
                              <TrendBadge trend={c.trend} value={Math.abs(diffPercent)} size="sm" />
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
                                c.last_in_stock === true ? "bg-price-down dark:bg-price-down" : "bg-muted dark:bg-muted",
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
      </section>
    </div>
  );
}
