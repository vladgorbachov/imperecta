/**
 * Products page with filters panel, toolbar, sortable table, pagination.
 *
 * i18n keys used:
 * - nav.products, products.*, filters.*, common.*
 */

import { useState, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Plus,
  Upload,
  Search,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Package,
  SlidersHorizontal,
} from "lucide-react";
import { formatPrice, formatRelativeTime } from "@/lib/formatters";
import { useDebounce } from "@/hooks/useDebounce";
import { useProducts, useProductCategories } from "@/hooks/useProducts";
import { DEFAULT_FILTERS } from "@/data/filters";
import { FiltersPanel } from "@/components/products/FiltersPanel";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

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

type SortKey =
  | "name"
  | "current_price"
  | "min_competitor_price"
  | "max_competitor_price"
  | "competitor_count"
  | "last_checked_at";
type SortDir = "asc" | "desc";

const PAGE_SIZES = [20, 50, 100] as const;

function SortIcon({ sortKey, currentKey, dir }: { sortKey: SortKey; currentKey: SortKey | null; dir: SortDir }) {
  if (currentKey !== sortKey) {
    return <ArrowUpDown className="size-4 shrink-0 opacity-50" />;
  }
  return dir === "asc" ? (
    <ArrowUp className="size-4 shrink-0" />
  ) : (
    <ArrowDown className="size-4 shrink-0" />
  );
}

export function ProductsPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const locale = i18n.language;

  const [searchRaw, setSearchRaw] = useState("");
  const [category, setCategory] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(20);
  const [sortKey, setSortKey] = useState<SortKey | null>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [filtersSheetOpen, setFiltersSheetOpen] = useState(false);
  const [activeFilters, setActiveFilters] = useState<Record<string, string[]>>({});
  const [priceRange, setPriceRange] = useState({
    min: 0,
    max: 200000,
    currentMin: 0,
    currentMax: 200000,
  });

  const search = useDebounce(searchRaw, 300);
  const categoryParam = category && category !== "all" ? category : undefined;

  const { products: apiProducts, total: apiTotal, isLoading } = useProducts({
    search: search || undefined,
    category: categoryParam,
    page,
    limit: pageSize,
  });
  const { data: categories = [] } = useProductCategories();

  const filterConfigs = DEFAULT_FILTERS;

  const handleFilterChange = useCallback((filterId: string, values: string[]) => {
    setActiveFilters((prev) => {
      const next = { ...prev };
      if (values.length === 0) {
        delete next[filterId];
      } else {
        next[filterId] = values;
      }
      return next;
    });
    setPage(1);
  }, []);

  const handlePriceChange = useCallback((min: number, max: number) => {
    setPriceRange((prev) => ({ ...prev, currentMin: min, currentMax: max }));
    setPage(1);
  }, []);

  const handleResetFilters = useCallback(() => {
    setActiveFilters({});
    setPriceRange((prev) => ({
      ...prev,
      currentMin: prev.min,
      currentMax: prev.max,
    }));
    setPage(1);
  }, []);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    Object.values(activeFilters).forEach((arr) => {
      count += arr.length;
    });
    if (priceRange.currentMin !== priceRange.min || priceRange.currentMax !== priceRange.max) {
      count += 1;
    }
    return count;
  }, [activeFilters, priceRange]);

  const handleSort = useCallback((key: SortKey) => {
    setSortKey((prev) => {
      if (prev === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortDir("asc");
      }
      return key;
    });
  }, []);

  const filteredProducts = useMemo(() => {
    const list: ProductRow[] = apiProducts.map((p) => ({
      id: p.id,
      name: p.name,
      sku: p.sku,
      category: p.category,
      current_price: p.current_price,
      min_competitor_price: p.min_competitor_price,
      max_competitor_price: p.max_competitor_price,
      competitor_count: p.competitor_count,
      last_checked_at: p.last_checked_at,
    }));

    if (priceRange.currentMin > priceRange.min || priceRange.currentMax < priceRange.max) {
      return list.filter(
        (p) =>
          p.current_price >= priceRange.currentMin && p.current_price <= priceRange.currentMax
      );
    }
    return list;
  }, [apiProducts, priceRange]);

  const sortedProducts = useMemo(() => {
    const list = [...filteredProducts];
    if (!sortKey) return list;
    list.sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return sortDir === "asc" ? 1 : -1;
      if (bVal == null) return sortDir === "asc" ? -1 : 1;
      if (sortKey === "last_checked_at") {
        const aTime = new Date(aVal as string).getTime();
        const bTime = new Date(bVal as string).getTime();
        const cmp = aTime - bTime;
        return sortDir === "asc" ? cmp : -cmp;
      }
      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortDir === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      const cmp = (aVal as number) - (bVal as number);
      return sortDir === "asc" ? cmp : -cmp;
    });
    return list;
  }, [filteredProducts, sortKey, sortDir]);

  const total = apiTotal;
  const totalPages = Math.ceil(total / pageSize) || 1;
  const clampedPage = Math.min(page, totalPages) || 1;
  const start = (clampedPage - 1) * pageSize;
  const paginatedProducts = sortedProducts;

  const hasFilters =
    !!search ||
    (!!category && category !== "all") ||
    activeFilterCount > 0;
  const isEmpty = filteredProducts.length === 0;

  const clearFilters = () => {
    setSearchRaw("");
    setCategory("all");
    handleResetFilters();
    setPage(1);
  };

  const handleImportCsv = () => {
    navigate("/import");
  };

  const handleAddProduct = () => {
    navigate("/import");
  };

  const filtersPanelContent = (
    <FiltersPanel
      category={category}
      filters={filterConfigs}
      activeFilters={activeFilters}
      priceRange={priceRange}
      onFilterChange={handleFilterChange}
      onPriceChange={handlePriceChange}
      onReset={handleResetFilters}
    />
  );

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="nav.products"
        actions={
          <div className="flex w-full flex-wrap gap-2 sm:w-auto">
            <Button variant="outline" size="sm" onClick={handleImportCsv}>
              <Upload className="mr-2 size-4" />
              {t("products.importCsv")}
            </Button>
            <Button size="sm" onClick={handleAddProduct}>
              <Plus className="mr-2 size-4" />
              {t("products.addProduct")}
            </Button>
          </div>
        }
      />

      {/* Toolbar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="flex w-full flex-col gap-4 sm:flex-row sm:items-center sm:gap-2 lg:w-auto">
          {/* Filters toggle — tablet/mobile */}
          <Button
            variant="outline"
            size="sm"
            className="flex lg:hidden"
            onClick={() => setFiltersSheetOpen(true)}
            aria-label={t("filters.button")}
          >
            <SlidersHorizontal className="mr-2 size-4" />
            {t("filters.button")}
            {activeFilterCount > 0 && (
              <Badge variant="secondary" className="ml-2 size-5 px-1 text-xs">
                {activeFilterCount}
              </Badge>
            )}
          </Button>

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
        </div>
      </div>

      {/* Main layout: filters + table */}
      <div className="mt-4 flex min-h-0 flex-1 gap-4">
        {/* Desktop: filters panel */}
        <div className="hidden lg:block lg:h-[calc(100vh-16rem)] lg:shrink-0">
          {filtersPanelContent}
        </div>

        {/* Right content: table */}
        <div className="min-w-0 flex-1 space-y-4">
          <div className="overflow-hidden rounded-lg border border-border dark:border-border">
            {isLoading ? (
              <div className="p-4">
                <div className="space-y-2">
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
                action={{ label: "products.addProduct", onClick: handleAddProduct }}
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
              <div className="max-h-[calc(100vh-20rem)] overflow-x-auto overflow-y-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead
                        className="sticky top-0 z-10 cursor-pointer bg-background hover:bg-muted/50 dark:bg-background dark:hover:bg-muted/50"
                        onClick={() => handleSort("name")}
                      >
                        <div className="flex items-center gap-1">
                          {t("products.name")}
                          <SortIcon sortKey="name" currentKey={sortKey} dir={sortDir} />
                        </div>
                      </TableHead>
                      <TableHead
                        className="sticky top-0 z-10 cursor-pointer bg-background hover:bg-muted/50 dark:bg-background dark:hover:bg-muted/50"
                        onClick={() => handleSort("current_price")}
                      >
                        <div className="flex items-center gap-1">
                          {t("products.myPrice")}
                          <SortIcon sortKey="current_price" currentKey={sortKey} dir={sortDir} />
                        </div>
                      </TableHead>
                      <TableHead
                        className="sticky top-0 z-10 hidden cursor-pointer bg-background hover:bg-muted/50 lg:table-cell dark:bg-background dark:hover:bg-muted/50"
                        onClick={() => handleSort("min_competitor_price")}
                      >
                        <div className="flex items-center gap-1">
                          {t("products.minCompetitorPrice")}
                          <SortIcon sortKey="min_competitor_price" currentKey={sortKey} dir={sortDir} />
                        </div>
                      </TableHead>
                      <TableHead
                        className="sticky top-0 z-10 hidden cursor-pointer bg-background hover:bg-muted/50 lg:table-cell dark:bg-background dark:hover:bg-muted/50"
                        onClick={() => handleSort("max_competitor_price")}
                      >
                        <div className="flex items-center gap-1">
                          {t("products.maxPrice")}
                          <SortIcon sortKey="max_competitor_price" currentKey={sortKey} dir={sortDir} />
                        </div>
                      </TableHead>
                      <TableHead
                        className="sticky top-0 z-10 hidden cursor-pointer bg-background hover:bg-muted/50 lg:table-cell dark:bg-background dark:hover:bg-muted/50"
                        onClick={() => handleSort("competitor_count")}
                      >
                        <div className="flex items-center gap-1">
                          {t("products.competitorCount")}
                          <SortIcon sortKey="competitor_count" currentKey={sortKey} dir={sortDir} />
                        </div>
                      </TableHead>
                      <TableHead className="sticky top-0 z-10 bg-background dark:bg-background">
                        {t("products.position")}
                      </TableHead>
                      <TableHead
                        className="sticky top-0 z-10 hidden cursor-pointer bg-background hover:bg-muted/50 sm:table-cell dark:bg-background dark:hover:bg-muted/50"
                        onClick={() => handleSort("last_checked_at")}
                      >
                        <div className="flex items-center gap-1">
                          {t("products.lastParsing")}
                          <SortIcon sortKey="last_checked_at" currentKey={sortKey} dir={sortDir} />
                        </div>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedProducts.map((p) => (
                      <ProductTableRow
                        key={p.id}
                        product={p}
                        locale={locale}
                        onRowClick={() => navigate(`/products/${p.id}`)}
                      />
                    ))}
                  </TableBody>
                </Table>
              </div>
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

      {/* Filters Sheet — tablet/mobile */}
      <Sheet open={filtersSheetOpen} onOpenChange={setFiltersSheetOpen}>
        <SheetContent side="left" className="w-64 p-0">
          <SheetHeader className="sr-only">
            <SheetTitle>{t("filters.title")}</SheetTitle>
          </SheetHeader>
          <div className="h-full overflow-hidden">
            {filtersPanelContent}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

function ProductTableRow({
  product,
  locale,
  onRowClick,
}: {
  product: ProductRow;
  locale: string;
  onRowClick: () => void;
}) {
  const { t } = useTranslation();
  const minPrice = product.min_competitor_price;
  const myPrice = product.current_price;
  const diffPercent =
    minPrice != null && minPrice > 0 ? ((myPrice - minPrice) / minPrice) * 100 : null;
  const isOverpriced = diffPercent != null && diffPercent > 0;
  const isCheaper = diffPercent != null && diffPercent < 0;

  return (
    <TableRow
      className="cursor-pointer transition-colors hover:bg-muted/50 dark:hover:bg-muted/50"
      onClick={onRowClick}
    >
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
      <TableCell className="hidden lg:table-cell">
        {minPrice != null ? formatPrice(minPrice, "RUB", locale) : t("common.dash")}
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        {product.max_competitor_price != null
          ? formatPrice(product.max_competitor_price, "RUB", locale)
          : t("common.dash")}
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        {product.competitor_count}
      </TableCell>
      <TableCell>
        {diffPercent != null ? (
          <Badge
            variant={isOverpriced ? "destructive" : "secondary"}
            className={cn(
              "w-fit text-xs",
              isOverpriced &&
                "bg-price-up/15 text-price-up border-price-up/30 dark:bg-price-up/20 dark:text-price-up dark:border-price-up/40",
              isCheaper &&
                "bg-price-down/15 text-price-down border-price-down/30 dark:bg-price-down/20 dark:text-price-down dark:border-price-down/40"
            )}
          >
            {isOverpriced
              ? t("products.overpricedBy", { percent: diffPercent.toFixed(1) })
              : t("products.cheaperBy", { percent: Math.abs(diffPercent).toFixed(1) })}
          </Badge>
        ) : (
          t("common.dash")
        )}
      </TableCell>
      <TableCell className="hidden text-muted-foreground sm:table-cell dark:text-muted-foreground">
        {product.last_checked_at
          ? formatRelativeTime(product.last_checked_at, locale)
          : t("common.dash")}
      </TableCell>
    </TableRow>
  );
}
