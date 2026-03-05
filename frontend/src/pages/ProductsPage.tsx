/**
 * Products page with toolbar, sortable table, pagination.
 *
 * i18n keys used:
 * - nav.products
 * - products.search, products.category, products.allCategories
 * - products.importCsv, products.addProduct
 * - products.name, products.sku, products.myPrice
 * - products.minCompetitorPrice, products.maxPrice, products.competitorCount
 * - products.position, products.overpricedBy, products.cheaperBy
 * - products.lastParsing, products.noProducts, products.noProductsHint
 * - products.noResults, products.clearFilters
 * - products.paginationShown
 * - common.dash
 */

import { useState, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Plus, Upload, Search, ArrowUpDown, ArrowUp, ArrowDown, Package } from "lucide-react";
import { formatPrice, formatRelativeTime } from "@/lib/formatters";
import { useDebounce } from "@/hooks/useDebounce";
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

type SortKey = "name" | "current_price" | "min_competitor_price" | "max_competitor_price" | "competitor_count" | "last_checked_at";
type SortDir = "asc" | "desc";

// TODO: API — replace with useProducts() / productsApi.list()
const MOCK_PRODUCTS: ProductRow[] = [
  { id: "1", name: "Смартфон Galaxy A55", sku: "GAL-A55-128", category: "Электроника", current_price: 32490, min_competitor_price: 28990, max_competitor_price: 32990, competitor_count: 5, last_checked_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString() },
  { id: "2", name: "Наушники Sony WH-1000XM5", sku: "SNY-XM5", category: "Электроника", current_price: 28900, min_competitor_price: 27500, max_competitor_price: 31500, competitor_count: 4, last_checked_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString() },
  { id: "3", name: "Пылесос Dyson V15", sku: "DYS-V15", category: "Бытовая техника", current_price: 79990, min_competitor_price: 75990, max_competitor_price: 89990, competitor_count: 3, last_checked_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString() },
  { id: "4", name: "Кофемашина DeLonghi Magnifica", sku: "DLG-MAG", category: "Бытовая техника", current_price: 42900, min_competitor_price: 45900, max_competitor_price: 49900, competitor_count: 2, last_checked_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString() },
  { id: "5", name: "Умные часы Apple Watch SE", sku: "APL-WSE", category: "Гаджеты", current_price: 32990, min_competitor_price: 29990, max_competitor_price: 35990, competitor_count: 6, last_checked_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString() },
  { id: "6", name: "Телевизор Samsung 55 QLED", sku: "SAM-55Q", category: "Электроника", current_price: 89990, min_competitor_price: 84990, max_competitor_price: 94990, competitor_count: 4, last_checked_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString() },
  { id: "7", name: "Ноутбук Lenovo IdeaPad", sku: "LNV-IDP", category: "Электроника", current_price: 54990, min_competitor_price: 52990, max_competitor_price: 59990, competitor_count: 5, last_checked_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString() },
  { id: "8", name: "Микроволновка LG NeoChef", sku: "LG-NC", category: "Бытовая техника", current_price: 12990, min_competitor_price: 11990, max_competitor_price: 13990, competitor_count: 3, last_checked_at: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString() },
  { id: "9", name: "Блендер Braun Multiquick", sku: "BRN-MQ", category: "Бытовая техника", current_price: 8990, min_competitor_price: 8490, max_competitor_price: 9990, competitor_count: 2, last_checked_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString() },
  { id: "10", name: "Робот-пылесос Xiaomi S10", sku: "XMI-S10", category: "Бытовая техника", current_price: 34990, min_competitor_price: 32990, max_competitor_price: 37990, competitor_count: 4, last_checked_at: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString() },
  { id: "11", name: "Клавиатура Logitech MX Keys", sku: "LOG-MXK", category: "Аксессуары", current_price: 12990, min_competitor_price: 11990, max_competitor_price: 13990, competitor_count: 3, last_checked_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString() },
  { id: "12", name: "Монитор Dell 27 S2722QC", sku: "DEL-27S", category: "Электроника", current_price: 32990, min_competitor_price: 30990, max_competitor_price: 35990, competitor_count: 2, last_checked_at: new Date(Date.now() - 36 * 60 * 60 * 1000).toISOString() },
  { id: "13", name: "Колонка JBL Charge 5", sku: "JBL-CH5", category: "Электроника", current_price: 14990, min_competitor_price: 13990, max_competitor_price: 16990, competitor_count: 5, last_checked_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString() },
  { id: "14", name: "Планшет Samsung Tab S9", sku: "SAM-TS9", category: "Гаджеты", current_price: 49990, min_competitor_price: 46990, max_competitor_price: 54990, competitor_count: 4, last_checked_at: new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString() },
  { id: "15", name: "Фитнес-браслет Xiaomi Band 8", sku: "XMI-B8", category: "Гаджеты", current_price: 3990, min_competitor_price: 3690, max_competitor_price: 4490, competitor_count: 6, last_checked_at: new Date(Date.now() - 30 * 60 * 60 * 1000).toISOString() },
];

const MOCK_CATEGORIES = ["Электроника", "Бытовая техника", "Гаджеты", "Аксессуары"];

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
  const [isLoading] = useState(false);

  const search = useDebounce(searchRaw, 300);

  const handleSort = useCallback((key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortDir("asc");
    }
    setSortKey(key);
  }, [sortKey]);

  const filteredProducts = useMemo(() => {
    let list = [...MOCK_PRODUCTS];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          (p.sku?.toLowerCase().includes(q) ?? false)
      );
    }
    if (category && category !== "all") {
      list = list.filter((p) => p.category === category);
    }
    return list;
  }, [search, category]);

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
        return sortDir === "asc"
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }
      const cmp = (aVal as number) - (bVal as number);
      return sortDir === "asc" ? cmp : -cmp;
    });
    return list;
  }, [filteredProducts, sortKey, sortDir]);

  const total = sortedProducts.length;
  const totalPages = Math.ceil(total / pageSize) || 1;
  const clampedPage = Math.min(page, totalPages) || 1;
  const start = (clampedPage - 1) * pageSize;
  const paginatedProducts = sortedProducts.slice(start, start + pageSize);

  const hasFilters = !!search || (!!category && category !== "all");
  const isEmpty = filteredProducts.length === 0;

  const clearFilters = () => {
    setSearchRaw("");
    setCategory("all");
    setPage(1);
  };

  const handleImportCsv = () => {
    // TODO: API — importApi.uploadProductsCsv
  };

  const handleAddProduct = () => {
    // TODO: API — open add dialog
  };

  return (
    <div className="space-y-6">
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
          <div className="relative w-full lg:w-72">
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
              {MOCK_CATEGORIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Table */}
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
    minPrice != null && minPrice > 0
      ? ((myPrice - minPrice) / minPrice) * 100
      : null;
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
        {minPrice != null
          ? formatPrice(minPrice, "RUB", locale)
          : t("common.dash")}
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
              ? t("products.overpricedBy", {
                  percent: diffPercent.toFixed(1),
                })
              : t("products.cheaperBy", {
                  percent: Math.abs(diffPercent).toFixed(1),
                })}
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
