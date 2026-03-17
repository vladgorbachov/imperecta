// MOBILE-2026: fully responsive + bottom nav + drawer

/**
 * AI Product Intelligence Hub: toolbar, at-risk widget, table/cards with AI recommendations.
 * i18n keys: nav.products, products.*, common.*
 */

import { useState, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Plus,
  Upload,
  Search,
  Sparkles,
  MoreHorizontal,
  Package,
} from "lucide-react";
import { toast } from "sonner";
import { formatPrice } from "@/lib/formatters";
import { useDebounce } from "@/hooks/useDebounce";
import { useProducts, useProductCategories } from "@/hooks/useProducts";
import { usePlanLimits } from "@/hooks/usePlanLimits";
import { PlanLimitBanner } from "@/components/ui-custom/PlanLimitBanner";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendBadge } from "@/components/ui-custom/TrendBadge";
import { cn } from "@/lib/utils";

// TODO: GET /api/products/{id}/ai-recommendation
type AiRecommendation = "lower" | "keep" | "raise";

interface ProductRow {
  id: string;
  name: string;
  sku: string | null;
  category: string | null;
  current_price: number;
  min_competitor_price: number | null;
  max_competitor_price: number | null;
  competitor_count: number;
  last_checked_at: string | null;
}

const PAGE_SIZES = [20, 50, 100] as const;

/** 7d change derived from min_competitor vs current (no historical API). */
function computePricePosition(
  current: number,
  minComp: number | null
): { trend: "up" | "down" | "stable"; value: number } {
  if (minComp == null || minComp <= 0) return { trend: "stable", value: 0 };
  const diff = ((current - minComp) / minComp) * 100;
  if (diff > 2) return { trend: "up", value: Math.abs(diff) };
  if (diff < -2) return { trend: "down", value: Math.abs(diff) };
  return { trend: "stable", value: 0 };
}

/** Recommendation based on price position vs competitors. */
function computeRecommendation(
  current: number,
  minComp: number | null
): { type: AiRecommendation; label: string } {
  if (minComp == null || minComp <= 0) return { type: "keep", label: "keep" };
  const diff = ((current - minComp) / minComp) * 100;
  if (diff > 8) return { type: "lower", label: "lower5" };
  if (diff < -5) return { type: "raise", label: "raise" };
  return { type: "keep", label: "keep" };
}

/** Margin percent: (current - minComp) / current * 100. */
function computeMarginPercent(current: number, minComp: number | null): number | null {
  if (minComp == null || minComp <= 0) return null;
  const margin = ((current - minComp) / current) * 100;
  return Math.round(margin * 10) / 10;
}

/** Top at-risk products (most overpriced vs competitors). */
function getAtRiskProducts(
  products: ProductRow[],
  limit: number
): Array<{ product: ProductRow; risk: "high" | "medium"; reason: string }> {
  return products
    .filter((p) => p.min_competitor_price != null && p.min_competitor_price > 0)
    .map((p) => {
      const diff = ((p.current_price - (p.min_competitor_price ?? 0)) / (p.min_competitor_price ?? 1)) * 100;
      const risk: "high" | "medium" = diff > 15 ? "high" : diff > 5 ? "medium" : "medium";
      const reason =
        diff > 15
          ? "competitorDropped20"
          : diff > 5
            ? "competitorDropped10"
            : "aboveMarket";
      return { product: p, risk, reason };
    })
    .filter((s) => s.risk === "high" || s.reason !== "aboveMarket")
    .sort((a, b) => {
      const aDiff =
        ((a.product.current_price - (a.product.min_competitor_price ?? 0)) /
          (a.product.min_competitor_price ?? 1)) *
        100;
      const bDiff =
        ((b.product.current_price - (b.product.min_competitor_price ?? 0)) /
          (b.product.min_competitor_price ?? 1)) *
        100;
      return bDiff - aDiff;
    })
    .slice(0, limit);
}

export function ProductsPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const locale = i18n.language;

  const [searchRaw, setSearchRaw] = useState("");
  const [category, setCategory] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(20);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const search = useDebounce(searchRaw, 300);
  const categoryParam = category && category !== "all" ? category : undefined;

  const { canAddProducts } = usePlanLimits();
  const { products: apiProducts, total: apiTotal, isLoading } = useProducts({
    search: search || undefined,
    category: categoryParam,
    page,
    limit: pageSize,
  });
  const { data: categories = [] } = useProductCategories();

  const productRows = useMemo(
    (): ProductRow[] =>
      apiProducts.map((p) => ({
        id: p.id,
        name: p.name,
        sku: p.sku,
        category: p.category,
        current_price: p.current_price,
        min_competitor_price: p.min_competitor_price,
        max_competitor_price: p.max_competitor_price,
        competitor_count: p.competitor_count,
        last_checked_at: p.last_checked_at,
      })),
    [apiProducts]
  );

  const atRiskItems = useMemo(
    () => getAtRiskProducts(productRows, 5),
    [productRows]
  );

  const total = apiTotal;
  const totalPages = Math.ceil(total / pageSize) || 1;
  const clampedPage = Math.min(page, totalPages) || 1;
  const start = (clampedPage - 1) * pageSize;
  const hasFilters = !!search || (!!category && category !== "all");
  const isEmpty = productRows.length === 0;

  const handleOptimizeAll = useCallback(() => {
    toast.info(t("products.aiAnalyzing"));
  }, [t]);

  const handleAddProduct = useCallback(() => {
    navigate("/import");
  }, [navigate]);

  const handleImportCsv = useCallback(() => {
    navigate("/import");
  }, [navigate]);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === productRows.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(productRows.map((p) => p.id)));
    }
  }, [productRows, selectedIds.size]);

  const handleParseSelected = useCallback(() => {
    if (selectedIds.size === 0) return;
    toast.info(t("products.parseStarted", { count: selectedIds.size }));
  }, [selectedIds.size, t]);

  const handleCreateAlertsSelected = useCallback(() => {
    if (selectedIds.size === 0) return;
    toast.info(t("products.alertsCreated", { count: selectedIds.size }));
  }, [selectedIds.size, t]);

  const clearFilters = useCallback(() => {
    setSearchRaw("");
    setCategory("all");
    setPage(1);
  }, []);

  return (
    <div className="flex h-full flex-col">
      <PlanLimitBanner className="mb-4" />
      <PageHeader
        title="nav.products"
        actions={
          <div className="flex w-full flex-wrap gap-2 sm:w-auto">
            <Button
              variant="outline"
              size="sm"
              onClick={handleImportCsv}
              disabled={!canAddProducts}
              title={!canAddProducts ? t("planLimit.cannotAdd") : undefined}
            >
              <Upload className="mr-2 size-4" />
              {t("products.importCsv")}
            </Button>
            <Button
              size="sm"
              onClick={handleAddProduct}
              disabled={!canAddProducts}
              title={!canAddProducts ? t("planLimit.cannotAdd") : undefined}
            >
              <Plus className="mr-2 size-4" />
              {t("products.addProduct")}
            </Button>
          </div>
        }
      />

      {/* Toolbar */}
      <div className="glass-card flex flex-col gap-4 rounded-xl p-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="flex w-full flex-col gap-4 sm:flex-row sm:items-center sm:gap-2 lg:w-auto">
          <div className="relative flex-1 lg:max-w-72">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground dark:text-muted-foreground" />
            <Input
              placeholder={t("products.search")}
              value={searchRaw}
              onChange={(e) => {
                setSearchRaw(e.target.value);
                setPage(1);
              }}
              className="w-full pl-9"
            />
          </div>
          <Select
            value={category}
            onValueChange={(v) => {
              setCategory(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-full sm:w-48">
              <SelectValue placeholder={t("products.allCategories")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("products.allCategories")}</SelectItem>
              {categories.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={handleOptimizeAll} className="hidden sm:inline-flex">
            <Sparkles className="mr-2 size-4" />
            {t("products.optimizeAllPrices")}
          </Button>
        </div>
      </div>

      {/* Bulk actions when selection */}
      {selectedIds.size > 0 && (
        <div
          className="flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2"
          style={{
            borderColor: "var(--glass-border)",
            background: "var(--glass-bg)",
          }}
        >
          <span className="text-sm font-medium">
            {t("products.selectedCount", { count: selectedIds.size })}
          </span>
          <Button variant="outline" size="sm" onClick={handleParseSelected}>
            {t("products.parseSelected")}
          </Button>
          <Button variant="outline" size="sm" onClick={handleCreateAlertsSelected}>
            {t("products.createAlerts")}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSelectedIds(new Set())}
          >
            {t("common.cancel")}
          </Button>
        </div>
      )}

      {/* Top 5 at-risk widget */}
      {!isLoading && atRiskItems.length > 0 && (
        <div className="space-y-2">
          <h3
            className="text-sm font-medium"
            style={{
              background: "linear-gradient(135deg, var(--foreground), var(--foreground-muted))",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              fontFamily: "var(--font-display)",
            }}
          >
            {t("products.topAtRisk")}
          </h3>
          <div className="flex gap-3 overflow-x-auto pb-2">
            {atRiskItems.map(({ product, risk, reason }) => (
              <button
                key={product.id}
                type="button"
                onClick={() => navigate(`/products/${product.id}`)}
                className="glass-card flex min-w-[200px] shrink-0 flex-col gap-1 rounded-xl p-3 text-left transition-colors hover:border-[var(--glass-border-hover)]"
              >
                <span className="truncate text-sm font-medium">{product.name}</span>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={risk === "high" ? "destructive" : "secondary"}
                    className={cn(
                      "text-xs border",
                      risk === "medium" &&
                        "bg-[var(--color-promo-bg)] text-[var(--color-promo)] border-[var(--color-promo-border)]"
                    )}
                  >
                    {risk === "high"
                      ? t("products.riskHigh")
                      : t("products.riskMedium")}
                  </Badge>
                </div>
                <span className="text-xs" style={{ color: "var(--foreground-muted)" }}>
                  {t(`products.reason.${reason}`)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Table (desktop) / Cards (mobile) */}
      <div className="mt-4 min-w-0 flex-1 space-y-4">
        <div className="glass-card overflow-hidden rounded-xl">
          {isLoading ? (
            <div className="p-4">
              <div className="grid grid-cols-2 gap-3 md:hidden">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-36 animate-pulse rounded-lg" />
                ))}
              </div>
              <div className="hidden space-y-2 md:block">
                {Array.from({ length: 7 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            </div>
          ) : isEmpty && !hasFilters ? (
            <EmptyState
              title="products.noProducts"
              description="products.noProductsHint"
              icon={Package}
              action={
                canAddProducts
                  ? { label: "products.addProduct", onClick: handleAddProduct }
                  : undefined
              }
            />
          ) : isEmpty && hasFilters ? (
            <div className="flex flex-col items-center justify-center gap-4 px-4 py-12">
              <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                {t("products.noResults")}
              </p>
              <Button variant="outline" onClick={clearFilters}>
                {t("products.clearFilters")}
              </Button>
            </div>
          ) : (
            <>
              {/* Mobile: card grid */}
              <div className="grid grid-cols-2 gap-3 p-4 md:hidden">
                {productRows.map((p) => (
                  <ProductCard
                    key={p.id}
                    product={p}
                    locale={locale}
                    isSelected={selectedIds.has(p.id)}
                    onSelect={() => toggleSelect(p.id)}
                    onRowClick={() => navigate(`/products/${p.id}`)}
                    t={t}
                  />
                ))}
              </div>
              {/* Desktop: table */}
              <div className="hidden max-h-[55vh] overflow-x-auto overflow-y-auto md:block sm:max-h-[calc(100vh-20rem)]">
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="w-10">
                        <Checkbox
                          checked={
                            productRows.length > 0 &&
                            selectedIds.size === productRows.length
                          }
                          onCheckedChange={toggleSelectAll}
                          aria-label={t("products.selectAll")}
                        />
                      </TableHead>
                      <TableHead>{t("products.name")}</TableHead>
                      <TableHead>{t("products.myPrice")}</TableHead>
                      <TableHead>{t("products.change7d")}</TableHead>
                      <TableHead className="hidden lg:table-cell">
                        {t("products.minCompetitorPrice")}
                      </TableHead>
                      <TableHead className="hidden xl:table-cell">
                        {t("products.marginForecast")}
                      </TableHead>
                      <TableHead>{t("products.recommendation")}</TableHead>
                      <TableHead className="w-10" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {productRows.map((p) => (
                      <ProductTableRow
                        key={p.id}
                        product={p}
                        locale={locale}
                        isSelected={selectedIds.has(p.id)}
                        onSelect={() => toggleSelect(p.id)}
                        onRowClick={() => navigate(`/products/${p.id}`)}
                      />
                    ))}
                  </TableBody>
                </Table>
              </div>
            </>
          )}
        </div>

        {/* Pagination */}
        {!isEmpty && !isLoading && total > 0 && (
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground dark:text-muted-foreground">
              {t("products.paginationShown", {
                from: start + 1,
                to: Math.min(start + pageSize, total),
                total,
              })}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={clampedPage <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                {t("common.back")}
              </Button>
              <span className="px-2 text-sm">
                {clampedPage} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={clampedPage >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                {t("common.next")}
              </Button>
              <Select
                value={String(pageSize)}
                onValueChange={(v) => {
                  setPageSize(Number(v));
                  setPage(1);
                }}
              >
                <SelectTrigger className="h-9 w-20">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PAGE_SIZES.map((s) => (
                    <SelectItem key={s} value={String(s)}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ProductCard({
  product,
  locale,
  isSelected,
  onSelect,
  onRowClick,
  t,
}: {
  product: ProductRow;
  locale: string;
  isSelected: boolean;
  onSelect: () => void;
  onRowClick: () => void;
  t: (key: string) => string;
}) {
  const minPrice = product.min_competitor_price;
  const change7d = computePricePosition(product.current_price, minPrice);
  const rec = computeRecommendation(product.current_price, minPrice);
  const recLabelKey =
    rec.type === "lower"
      ? "products.recommendationLower5"
      : rec.type === "raise"
        ? "products.recommendationRaise"
        : "products.recommendationKeep";

  return (
    <button
      type="button"
      onClick={onRowClick}
      className="glass-card flex min-h-[120px] flex-col items-stretch gap-2 rounded-xl p-3 text-left transition-colors active:scale-[0.98] hover:border-[var(--glass-border-hover)]"
    >
      <div className="flex items-start justify-between gap-1">
        <Checkbox
          checked={isSelected}
          onCheckedChange={onSelect}
          onClick={(e) => e.stopPropagation()}
          aria-label={t("products.selectProduct", { name: product.name })}
          className="shrink-0"
        />
        <span
          className={cn(
            "rounded-md border px-1.5 py-0 text-[10px] font-medium",
            rec.type === "lower" && "border-[var(--color-price-down-border)]",
            rec.type === "raise" && "border-[var(--accent-border)]",
            rec.type === "keep" && "border-[var(--glass-border)]"
          )}
          style={{
            background:
              rec.type === "lower"
                ? "var(--color-price-down-bg)"
                : rec.type === "raise"
                  ? "var(--accent-bg)"
                  : "var(--glass-bg)",
            color:
              rec.type === "lower"
                ? "var(--color-price-down)"
                : rec.type === "raise"
                  ? "var(--accent)"
                  : "var(--foreground-muted)",
            boxShadow:
              rec.type === "lower"
                ? "0 0 8px var(--glow-green)"
                : rec.type === "raise"
                  ? "0 0 8px var(--accent-glow)"
                  : undefined,
          }}
        >
          {t(recLabelKey)}
        </span>
      </div>
      <span className="line-clamp-2 text-sm font-medium">{product.name}</span>
      <div className="mt-auto flex items-center justify-between">
        <span
          className="text-sm font-semibold"
          style={{ fontFamily: "var(--font-display)", color: "var(--foreground)" }}
        >
          {formatPrice(product.current_price, "RUB", locale)}
        </span>
        <TrendBadge trend={change7d.trend} value={change7d.value} size="sm" />
      </div>
    </button>
  );
}

function ProductTableRow({
  product,
  locale,
  isSelected,
  onSelect,
  onRowClick,
}: {
  product: ProductRow;
  locale: string;
  isSelected: boolean;
  onSelect: () => void;
  onRowClick: () => void;
}) {
  const { t } = useTranslation();
  const minPrice = product.min_competitor_price;
  const change7d = computePricePosition(product.current_price, minPrice);
  const rec = computeRecommendation(product.current_price, minPrice);
  const marginForecast = computeMarginPercent(product.current_price, minPrice);

  const recLabelKey =
    rec.type === "lower"
      ? "products.recommendationLower5"
      : rec.type === "raise"
        ? "products.recommendationRaise"
        : "products.recommendationKeep";

  return (
    <TableRow
      className="cursor-pointer transition-colors hover:bg-muted/50 dark:hover:bg-muted/50"
      onClick={onRowClick}
    >
      <TableCell onClick={(e) => e.stopPropagation()}>
        <Checkbox
          checked={isSelected}
          onCheckedChange={onSelect}
          aria-label={t("products.selectProduct", { name: product.name })}
        />
      </TableCell>
      <TableCell>
        <div className="flex flex-col">
          <span className="font-medium">{product.name}</span>
          <span className="text-xs text-muted-foreground dark:text-muted-foreground">
            {product.sku ?? t("common.dash")}
          </span>
        </div>
      </TableCell>
      <TableCell>
        {formatPrice(product.current_price, "RUB", locale)}
      </TableCell>
      <TableCell>
        <TrendBadge
          trend={change7d.trend}
          value={change7d.value}
          size="sm"
        />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        {minPrice != null
          ? formatPrice(minPrice, "RUB", locale)
          : t("common.dash")}
      </TableCell>
      <TableCell className="hidden xl:table-cell">
        {marginForecast != null ? `${marginForecast}%` : t("common.dash")}
      </TableCell>
      <TableCell>
        <span
          className={cn(
            "inline-flex rounded-md border px-2 py-0.5 text-xs font-medium",
            rec.type === "lower" && "border-[var(--color-price-down-border)]",
            rec.type === "raise" && "border-[var(--accent-border)]",
            rec.type === "keep" && "border-[var(--glass-border)]"
          )}
          style={{
            background:
              rec.type === "lower"
                ? "var(--color-price-down-bg)"
                : rec.type === "raise"
                  ? "var(--accent-bg)"
                  : "var(--glass-bg)",
            color:
              rec.type === "lower"
                ? "var(--color-price-down)"
                : rec.type === "raise"
                  ? "var(--accent)"
                  : "var(--foreground-muted)",
            boxShadow:
              rec.type === "lower"
                ? "0 0 8px var(--glow-green)"
                : rec.type === "raise"
                  ? "0 0 8px var(--accent-glow)"
                  : undefined,
          }}
        >
          {t(recLabelKey)}
        </span>
      </TableCell>
      <TableCell onClick={(e) => e.stopPropagation()}>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="size-8">
              <MoreHorizontal className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onRowClick()}>
              {t("products.viewDetail")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  );
}
