/**
 * Displays products from global marketplace pool.
 *
 * Features:
 * - Search by title (debounced 500ms)
 * - Filter by marketplace (dropdown from /api/pool/categories)
 * - Sort by date, alphabet, price, trend, volatility
 * - Pagination with configurable page size (20/50/100)
 * - Each product row: image, title (clickable), marketplace badge, price, price change
 */

import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Bookmark, Download, Rows2, Rows4, Search, Trash2 } from "lucide-react";
import { PriceDisplay } from "@/components/ui-custom/PriceDisplay";
import { useDebounce } from "@/hooks/useDebounce";
import { usePoolProducts, usePoolCategories } from "@/hooks/usePoolProducts";
import { useMarketplaceLabelFormatter } from "@/hooks/useMarketplaceLabel";
import { MarketplaceBadge } from "@/components/ui-custom/MarketplaceBadge";
import { Scrollable } from "@/components/ui/Scrollable";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { ErrorState } from "@/components/ui-custom/ErrorState";
import { ProductPeek } from "@/components/products/ProductPeek";
import { Package } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { productsApi, type PoolProductItem } from "@/api/products";

const PAGE_SIZES = [20, 50, 100] as const;
const SORT_OPTIONS = [
  { value: "recent", labelKey: "products.sort.recent" },
  { value: "name_asc", labelKey: "products.sort.nameAsc" },
  { value: "name_desc", labelKey: "products.sort.nameDesc" },
  { value: "price_asc", labelKey: "products.sort.priceAsc" },
  { value: "price_desc", labelKey: "products.sort.priceDesc" },
  { value: "trending", labelKey: "products.sort.trending" },
  { value: "gainers", labelKey: "products.sort.gainers" },
  { value: "losers", labelKey: "products.sort.losers" },
  { value: "volatile", labelKey: "products.sort.volatile" },
] as const;

/** Saved view: a named filter+sort snapshot, persisted per browser. */
interface SavedView {
  name: string;
  search: string;
  marketplaceId: string;
  sort: string;
}

const VIEWS_STORAGE_KEY = "imperecta_products_views";
const DENSITY_STORAGE_KEY = "imperecta_products_density";

function loadSavedViews(): SavedView[] {
  try {
    const raw = localStorage.getItem(VIEWS_STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as SavedView[]) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persistSavedViews(views: SavedView[]) {
  try {
    localStorage.setItem(VIEWS_STORAGE_KEY, JSON.stringify(views));
  } catch {
    // storage unavailable — views stay session-only
  }
}

function loadDensity(): "comfortable" | "compact" {
  try {
    return localStorage.getItem(DENSITY_STORAGE_KEY) === "compact"
      ? "compact"
      : "comfortable";
  } catch {
    return "comfortable";
  }
}

function exportCsv(items: PoolProductItem[]) {
  const header = ["title", "marketplace", "country", "price", "currency", "change_24h_pct", "url"];
  const escape = (value: unknown) => {
    const text = value == null ? "" : String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const rows = items.map((item) =>
    [
      item.title ?? "",
      item.marketplace_name ?? item.marketplace_domain ?? "",
      item.country_code ?? "",
      item.price ?? "",
      item.currency,
      item.price_change_pct ?? "",
      item.url,
    ]
      .map(escape)
      .join(","),
  );
  const csv = [header.join(","), ...rows].join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `imperecta-products-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function ProductThumbnail({ item }: { item: PoolProductItem }) {
  const letter = (item.title || "?")[0].toUpperCase();
  if (item.image_url) {
    return (
      <img
        src={item.image_url}
        alt=""
        className="size-10 shrink-0 rounded-md object-cover"
      />
    );
  }
  return (
    <div
      className="flex size-10 shrink-0 items-center justify-center rounded-md text-sm font-semibold"
      style={{
        background: "var(--glass-bg)",
        border: "1px solid var(--glass-border)",
        color: "var(--foreground-muted)",
      }}
    >
      {letter}
    </div>
  );
}

export function PoolProductsTab() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();

  const [searchRaw, setSearchRaw] = useState(() => searchParams.get("search") ?? "");
  const [marketplaceId, setMarketplaceId] = useState<string>("all");
  const [sort, setSort] = useState<string>("recent");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [peekItem, setPeekItem] = useState<PoolProductItem | null>(null);
  const [peekOpen, setPeekOpen] = useState(false);
  const [savedViews, setSavedViews] = useState<SavedView[]>(() => loadSavedViews());
  const [density, setDensity] = useState<"comfortable" | "compact">(() => loadDensity());

  useEffect(() => {
    try {
      localStorage.setItem(DENSITY_STORAGE_KEY, density);
    } catch {
      // storage unavailable
    }
  }, [density]);

  const [saveViewOpen, setSaveViewOpen] = useState(false);
  const [viewName, setViewName] = useState("");

  const saveCurrentView = () => {
    const name = viewName.trim();
    if (!name) {
      return;
    }
    const next = [
      ...savedViews.filter((view) => view.name !== name),
      { name, search: searchRaw, marketplaceId, sort },
    ];
    setSavedViews(next);
    persistSavedViews(next);
    setViewName("");
    setSaveViewOpen(false);
  };

  const applyView = (view: SavedView) => {
    setSearchRaw(view.search);
    setMarketplaceId(view.marketplaceId);
    setSort(view.sort);
    setPage(1);
  };

  const deleteView = (name: string) => {
    const next = savedViews.filter((view) => view.name !== name);
    setSavedViews(next);
    persistSavedViews(next);
  };

  /* P5: server-streamed CSV of the full filtered pool. */
  const exportFullPool = async () => {
    try {
      const response = await productsApi.exportPoolCsv({
        search: search.length >= 2 ? search : undefined,
        marketplace_id: marketplaceId !== "all" ? marketplaceId : undefined,
        sort: sort as Parameters<typeof usePoolProducts>[0]["sort"],
      });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = "imperecta_pool.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error(t("common.error"));
    }
  };

  const search = useDebounce(searchRaw, 500);
  const offset = (page - 1) * pageSize;
  const formatMarketplaceLabel = useMarketplaceLabelFormatter();

  const { data: categories = [] } = usePoolCategories();
  const { data, isLoading, isError, refetch } = usePoolProducts({
    search: search.length >= 2 ? search : undefined,
    marketplace_id: marketplaceId !== "all" ? marketplaceId : undefined,
    sort: sort as Parameters<typeof usePoolProducts>[0]["sort"],
    limit: pageSize,
    offset,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / pageSize) || 1;
  const clampedPage = Math.min(page, totalPages) || 1;
  const start = (clampedPage - 1) * pageSize;
  const hasFilters = search.length >= 2 || marketplaceId !== "all";
  const isEmpty = items.length === 0 && !isLoading;

  return (
    <div className="flex flex-col gap-4">
      {/* Toolbar */}
      <div className="surface-base flex flex-col gap-4 rounded-xl p-4 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="relative flex-1 lg:max-w-72">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder={t("products.searchByName")}
            value={searchRaw}
            onChange={(e) => {
              setSearchRaw(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9"
          />
        </div>
        <Select
          value={marketplaceId}
          onValueChange={(v) => {
            setMarketplaceId(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-full sm:w-48">
            <SelectValue placeholder={t("products.marketplace")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("products.allMarketplaces")}</SelectItem>
            {categories.map((c) => (
              <SelectItem key={c.marketplace_id} value={c.marketplace_id}>
                {formatMarketplaceLabel({
                  name: c.name,
                  domain: c.domain,
                  countryCode: c.country_code,
                }) || c.domain}{" "}
                ({c.listing_count})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={sort}
          onValueChange={(v) => {
            setSort(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-full sm:w-48">
            <SelectValue placeholder={t("products.sorting")} />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {t(o.labelKey)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="ms-auto flex items-center gap-1.5">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Bookmark className="me-1.5 size-3.5" />
                {t("products.views.label")}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="surface-overlay w-56">
              {savedViews.length === 0 ? (
                <p className="px-2 py-1.5 text-xs text-muted-foreground">
                  {t("products.views.empty")}
                </p>
              ) : (
                savedViews.map((view) => (
                  <DropdownMenuItem
                    key={view.name}
                    className="group flex items-center justify-between gap-2 focus:bg-[var(--glass-bg-hover)]"
                    onClick={() => applyView(view)}
                  >
                    <span className="min-w-0 flex-1 truncate">{view.name}</span>
                    <button
                      type="button"
                      aria-label={t("common.delete")}
                      className="shrink-0 text-muted-foreground opacity-0 transition-opacity hover:text-[var(--status-error)] group-hover:opacity-100"
                      onClick={(event) => {
                        event.stopPropagation();
                        deleteView(view.name);
                      }}
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </DropdownMenuItem>
                ))
              )}
              <DropdownMenuSeparator className="bg-[var(--glass-border)]" />
              <DropdownMenuItem
                className="focus:bg-[var(--glass-bg-hover)]"
                onClick={() => setSaveViewOpen(true)}
              >
                {t("products.views.saveCurrent")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Button
            variant="outline"
            size="sm"
            aria-label={t("products.density.toggle")}
            title={t("products.density.toggle")}
            onClick={() =>
              setDensity((value) => (value === "compact" ? "comfortable" : "compact"))
            }
          >
            {density === "compact" ? (
              <Rows2 className="size-3.5" />
            ) : (
              <Rows4 className="size-3.5" />
            )}
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" title={t("products.export.hint")}>
                <Download className="me-1.5 size-3.5" />
                {t("products.export.label")}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="surface-overlay">
              <DropdownMenuItem
                disabled={items.length === 0}
                className="focus:bg-[var(--glass-bg-hover)]"
                onClick={() => exportCsv(items)}
              >
                {t("products.export.visible")}
              </DropdownMenuItem>
              <DropdownMenuItem
                className="focus:bg-[var(--glass-bg-hover)]"
                onClick={() => void exportFullPool()}
              >
                {t("products.export.full")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <Dialog open={saveViewOpen} onOpenChange={setSaveViewOpen}>
        <DialogContent className="surface-overlay sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{t("products.views.saveCurrent")}</DialogTitle>
          </DialogHeader>
          <Input
            autoFocus
            value={viewName}
            onChange={(event) => setViewName(event.target.value)}
            placeholder={t("products.views.namePrompt")}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                saveCurrentView();
              }
            }}
          />
          <Button className="w-full" onClick={saveCurrentView} disabled={!viewName.trim()}>
            {t("common.save")}
          </Button>
        </DialogContent>
      </Dialog>

      {/* Table */}
      <div className="surface-base overflow-hidden rounded-xl">
        {isError ? (
          <ErrorState
            title="common.error"
            retry={{ label: "common.refresh", onClick: () => refetch() }}
          />
        ) : isLoading ? (
          <div className="p-4">
            <div className="space-y-2">
              {Array.from({ length: 7 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          </div>
        ) : isEmpty && !hasFilters ? (
          <EmptyState
            title="products.poolEmpty"
            description="products.poolEmptyHint"
            icon={Package}
          />
        ) : isEmpty && hasFilters ? (
          <EmptyState
            bordered
            icon={Package}
            title="products.noResults"
            description=""
            action={{
              label: "products.clearFilters",
              onClick: () => {
                setSearchRaw("");
                setMarketplaceId("all");
                setPage(1);
              },
            }}
          />
        ) : (
          <>
            <Scrollable
              axis="both"
              className="max-h-[55vh] overflow-auto scrollbar-none sm:max-h-[calc(100vh-20rem)]"
            >
              <Table
                className={cn(
                  density === "compact" &&
                    "[&_td]:py-1.5 [&_th]:py-2 [&_td]:text-xs",
                )}
              >
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-14" />
                    <TableHead>{t("products.name")}</TableHead>
                    <TableHead className="w-44">{t("products.marketplace")}</TableHead>
                    <TableHead className="w-32 text-right">{t("products.price")}</TableHead>
                    <TableHead className="w-32 text-right">{t("products.change24h")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item) => (
                    <TableRow
                      key={item.id}
                      className="cursor-pointer transition-colors"
                      data-trend={
                        item.price_change_pct != null && item.price_change_pct > 0
                          ? "up"
                          : item.price_change_pct != null && item.price_change_pct < 0
                            ? "down"
                            : undefined
                      }
                      onClick={() => {
                        setPeekItem(item);
                        setPeekOpen(true);
                      }}
                    >
                      <TableCell className="w-14">
                        <ProductThumbnail item={item} />
                      </TableCell>
                      <TableCell>
                        <span className="line-clamp-2 text-[0.9375rem] font-medium leading-snug">
                          {item.title || "—"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <MarketplaceBadge
                          marketplace={
                            item.marketplace_domain ||
                            item.marketplace_name ||
                            String(item.marketplace_id)
                          }
                          label={formatMarketplaceLabel({
                            name: item.marketplace_name,
                            domain: item.marketplace_domain,
                            countryCode: item.country_code,
                          })}
                          size="sm"
                        />
                      </TableCell>
                      <TableCell className="text-right">
                        <PriceDisplay
                          localAmount={item.price}
                          localCurrency={item.currency}
                          displayAmount={item.display_price}
                          displayCurrency={item.display_currency}
                          conversionAvailable={item.conversion_available}
                        />
                      </TableCell>
                      <TableCell className="text-right">
                        {item.price_change_pct != null ? (
                          <span
                            className={cn(
                              "font-medium font-mono tabular-nums text-right",
                              item.price_change_pct > 0 && "text-[var(--color-price-up)]",
                              item.price_change_pct < 0 && "text-[var(--color-price-down)]"
                            )}
                          >
                            {item.price_change_pct > 0 ? "+" : ""}
                            {item.price_change_pct.toFixed(2)}%
                          </span>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Scrollable>
          </>
        )}
      </div>

      {/* Pagination */}
      {!isEmpty && !isLoading && total > 0 && (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">
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

      <ProductPeek item={peekItem} open={peekOpen} onOpenChange={setPeekOpen} />
    </div>
  );
}
