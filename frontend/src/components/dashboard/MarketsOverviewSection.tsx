import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, Grid3X3, List, MoreHorizontal, Plus, Search } from "lucide-react";
import { toast } from "sonner";
import { marketsApi, marketsQueryKeys, type MarketsOverviewItem } from "@/api/markets";
import { productsApi } from "@/api/products";
import { Sparkline } from "@/components/ui-custom/Sparkline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useDebounce } from "@/hooks/useDebounce";
import { cn } from "@/lib/utils";

type MarketsTab = "volatile" | "trending" | "gainers" | "losers" | "recent";
type ViewMode = "table" | "cards";
type PriceChangeRange = "all" | "up5" | "down5" | "flat";

const PAGE_LIMIT = 200;
const MARKET_OVERVIEW_INITIAL_VISIBLE = 10;
const MARKET_OVERVIEW_EXPAND_STEP = 10;

const TABS: Array<{ key: MarketsTab; labelKey: string }> = [
  { key: "volatile", labelKey: "dashboard.market.mostVolatile" },
  { key: "trending", labelKey: "dashboard.market.trendingNow" },
  { key: "gainers", labelKey: "dashboard.market.topGainers" },
  { key: "losers", labelKey: "dashboard.market.topLosers" },
  { key: "recent", labelKey: "dashboard.market.recentlyUpdated" },
];

function formatPrice(value: number | null | undefined, currency: string | null | undefined, locale: string): string {
  if (value == null) {
    return "—";
  }
  const formatted = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
  return `${formatted} ${currency ?? ""}`.trim();
}

function formatPercent(value?: number | null): string {
  if (value == null) {
    return "—";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function parseDateValue(value?: string | null): number {
  if (!value) {
    return 0;
  }
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function ProductThumb({ item }: { item: MarketsOverviewItem }) {
  if (item.image_url) {
    return (
      <img
        src={item.image_url}
        alt={item.title ?? "Product"}
        className="size-10 rounded-md object-cover"
        loading="lazy"
      />
    );
  }
  return (
    <div className="flex size-10 items-center justify-center rounded-md border border-border text-xs text-muted-foreground">
      {(item.title ?? "?").slice(0, 1).toUpperCase()}
    </div>
  );
}

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-[var(--glass-bg)] p-3">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  );
}

export function MarketsOverviewSection() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const [activeTab, setActiveTab] = useState<MarketsTab>("volatile");
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [searchRaw, setSearchRaw] = useState("");
  const [sorting, setSorting] = useState<SortingState>([{ id: "price_change_pct_24h", desc: true }]);
  const [selectedMarketplaces, setSelectedMarketplaces] = useState<string[]>([]);
  const [priceChangeRange, setPriceChangeRange] = useState<PriceChangeRange>("all");
  const [historyOnly, setHistoryOnly] = useState(false);
  const [visibleCount, setVisibleCount] = useState(MARKET_OVERVIEW_INITIAL_VISIBLE);
  const debouncedSearch = useDebounce(searchRaw, 400);

  const overviewParams = useMemo(
    () => ({
      sort: activeTab,
      limit: PAGE_LIMIT,
      offset: 0,
      search: debouncedSearch.length >= 2 ? debouncedSearch : undefined,
    }),
    [activeTab, debouncedSearch],
  );

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: marketsQueryKeys.overview(overviewParams),
    queryFn: () => marketsApi.getOverview(overviewParams).then((response) => response.data),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
  const { data: marketplaceStats = [] } = useQuery({
    queryKey: marketsQueryKeys.poolMarketplaceStats(),
    queryFn: () => marketsApi.getPoolMarketplaceStats().then((response) => response.data),
    staleTime: 60_000,
  });
  const { data: poolStats } = useQuery({
    queryKey: marketsQueryKeys.poolStats(),
    queryFn: () => marketsApi.getPoolStats().then((response) => response.data),
    staleTime: 60_000,
  });

  const addProductMutation = useMutation({
    mutationFn: (item: MarketsOverviewItem) => {
      if (item.current_price == null || !item.currency) {
        throw new Error("Missing price data");
      }
      return productsApi.create({
        name: item.title ?? t("market.overview.productFallback"),
        current_price: item.current_price,
        currency: item.currency,
        url: item.url,
      });
    },
    onSuccess: () => toast.success(t("market.overview.addedToMyProducts")),
    onError: () => toast.error(t("market.overview.addToMyProductsFailed")),
  });

  const rawItems = useMemo(() => data?.items ?? [], [data?.items]);
  const filteredItems = useMemo(() => {
    return rawItems.filter((item) => {
      const inMarketplace = selectedMarketplaces.length === 0
        || selectedMarketplaces.includes(item.marketplace_domain ?? "");
      if (!inMarketplace) {
        return false;
      }
      if (historyOnly && (item.recent_prices?.length ?? 0) < 2) {
        return false;
      }
      const change = item.price_change_pct_24h ?? 0;
      if (priceChangeRange === "up5" && change <= 5) {
        return false;
      }
      if (priceChangeRange === "down5" && change >= -5) {
        return false;
      }
      if (priceChangeRange === "flat" && Math.abs(change) > 5) {
        return false;
      }
      return true;
    });
  }, [historyOnly, priceChangeRange, rawItems, selectedMarketplaces]);

  const kpis = useMemo(() => {
    const now = Date.now();
    const updated24h = filteredItems.filter((item) => now - parseDateValue(item.last_scraped_at) <= 24 * 60 * 60 * 1000).length;
    const changedMore5 = filteredItems.filter((item) => Math.abs(item.price_change_pct_24h ?? 0) > 5).length;
    const averageVolatility = filteredItems.length === 0
      ? 0
      : filteredItems.reduce((acc, item) => acc + Math.abs(item.price_change_pct_24h ?? 0), 0) / filteredItems.length;
    const lastUpdate = filteredItems.reduce((max, item) => Math.max(max, parseDateValue(item.last_scraped_at)), 0);

    return {
      total: String(poolStats?.total_products ?? data?.total ?? filteredItems.length),
      updated24h: String(updated24h),
      changedMore5: String(changedMore5),
      avgVolatility: `${averageVolatility.toFixed(2)}%`,
      lastUpdate: lastUpdate ? new Date(lastUpdate).toLocaleString(locale) : t("common.dash"),
    };
  }, [data?.total, filteredItems, locale, poolStats?.total_products, t]);

  useEffect(() => {
    setVisibleCount(MARKET_OVERVIEW_INITIAL_VISIBLE);
  }, [activeTab, debouncedSearch, historyOnly, priceChangeRange, selectedMarketplaces, viewMode]);

  const visibleItems = useMemo(
    () => filteredItems.slice(0, visibleCount),
    [filteredItems, visibleCount],
  );
  const hasMoreItems = visibleCount < filteredItems.length;
  const canCollapse = filteredItems.length > MARKET_OVERVIEW_INITIAL_VISIBLE
    && visibleCount > MARKET_OVERVIEW_INITIAL_VISIBLE;

  const columnHelper = createColumnHelper<MarketsOverviewItem>();
  const columns = useMemo(
    () => [
      columnHelper.display({
        id: "image",
        header: t("market.overview.image"),
        cell: ({ row }) => <ProductThumb item={row.original} />,
      }),
      columnHelper.accessor((row) => row.title ?? "", {
        id: "title",
        header: t("dashboard.market.product"),
        cell: ({ row }) => <span className="line-clamp-2 font-medium">{row.original.title ?? t("market.overview.untitled")}</span>,
      }),
      columnHelper.accessor((row) => row.marketplace_name ?? row.marketplace_domain ?? t("dashboard.market.marketplace"), {
        id: "marketplace",
        header: t("dashboard.market.marketplace"),
        cell: ({ getValue }) => <Badge variant="outline">{getValue()}</Badge>,
      }),
      columnHelper.accessor((row) => row.current_price ?? null, {
        id: "current_price",
        header: t("dashboard.market.price"),
        cell: ({ row }) => <span className="font-mono">{formatPrice(row.original.current_price, row.original.currency, locale)}</span>,
      }),
      columnHelper.accessor((row) => row.price_change_pct_24h ?? null, {
        id: "price_change_pct_24h",
        header: t("market.overview.change24h"),
        cell: ({ row }) => (
          <span className={cn("font-mono", (row.original.price_change_pct_24h ?? 0) > 0 && "text-[var(--color-price-down)]", (row.original.price_change_pct_24h ?? 0) < 0 && "text-[var(--color-price-up)]")}>
            {formatPercent(row.original.price_change_pct_24h)}
          </span>
        ),
      }),
      columnHelper.display({
        id: "sparkline",
        header: t("market.overview.sparkline7d"),
        cell: ({ row }) => (
          <Sparkline
            className="w-36"
            points={(row.original.recent_prices ?? []).map((point) => ({ date: point.date, price: point.price }))}
          />
        ),
      }),
      columnHelper.accessor((row) => row.last_scraped_at ?? "", {
        id: "last_scraped_at",
        header: t("market.overview.lastUpdated"),
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">
            {row.original.last_scraped_at ? new Date(row.original.last_scraped_at).toLocaleString(locale) : t("common.dash")}
          </span>
        ),
      }),
      columnHelper.accessor((row) => row.status, {
        id: "status",
        header: t("common.status"),
        cell: ({ getValue }) => (
          <Badge variant={getValue() === "active" ? "default" : "secondary"}>
            {getValue() === "active" ? t("market.overview.statusActive") : t("market.overview.statusInactive")}
          </Badge>
        ),
      }),
      columnHelper.display({
        id: "actions",
        header: t("common.actions"),
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <Button size="sm" asChild>
              <Link to={`/products/${row.original.product_id ?? row.original.id}`}>{t("market.overview.history")}</Link>
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" variant="outline" aria-label={t("common.actions")}>
                  <MoreHorizontal className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  disabled={row.original.current_price == null || !row.original.currency}
                  onClick={() => addProductMutation.mutate(row.original)}
                >
                  <Plus className="size-4" />
                  {t("market.overview.addToMy")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        ),
      }),
    ],
    [addProductMutation, columnHelper, locale, t],
  );

  const table = useReactTable({
    data: filteredItems,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const toggleMarketplace = (domain: string) => {
    setSelectedMarketplaces((prev) => (
      prev.includes(domain) ? prev.filter((value) => value !== domain) : [...prev, domain]
    ));
  };

  if (isError) {
    return (
      <div className="rounded-xl border border-[var(--color-price-up-border)] bg-[var(--color-price-up-bg)] p-4">
        <div className="mb-3 flex items-center gap-2 text-[var(--color-price-up)]">
          <AlertTriangle className="size-4" />
          {t("market.overview.loadFailed")}
        </div>
        <Button onClick={() => refetch()}>{t("common.refresh")}</Button>
      </div>
    );
  }

  return (
    <section className="space-y-3">
      <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-5">
        <KpiCard label={t("market.overview.kpi.totalPool")} value={kpis.total} />
        <KpiCard label={t("market.overview.kpi.updated24h")} value={kpis.updated24h} />
        <KpiCard label={t("market.overview.kpi.changedMore5")} value={kpis.changedMore5} />
        <KpiCard label={t("market.overview.kpi.avgVolatility")} value={kpis.avgVolatility} />
        <KpiCard label={t("market.overview.kpi.lastUpdate")} value={kpis.lastUpdate} />
      </div>

      <div className="liquid-glass rounded-xl border border-border bg-[var(--glass-bg)] p-3.5">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wide">{t("dashboard.market.title")}</h3>
          <div className="flex items-center gap-1 rounded-md border border-border p-1">
            <Button size="sm" variant={viewMode === "table" ? "secondary" : "ghost"} onClick={() => setViewMode("table")}>
              <List className="mr-1 size-4" />
              {t("market.overview.viewTable")}
            </Button>
            <Button size="sm" variant={viewMode === "cards" ? "secondary" : "ghost"} onClick={() => setViewMode("cards")}>
              <Grid3X3 className="mr-1 size-4" />
              {t("market.overview.viewCards")}
            </Button>
          </div>
        </div>

        <div className="mt-3 grid gap-2.5 lg:grid-cols-[1.4fr_1fr_180px]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchRaw}
              onChange={(event) => setSearchRaw(event.target.value)}
              placeholder={t("market.overview.searchPlaceholder")}
              className="pl-9"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {marketplaceStats.map((item) => (
              <button
                key={item.marketplace_domain}
                type="button"
                className={cn("rounded-full border px-2.5 py-0.5 text-xs", selectedMarketplaces.includes(item.marketplace_domain) ? "border-primary bg-primary/10 text-foreground" : "border-border text-muted-foreground")}
                onClick={() => toggleMarketplace(item.marketplace_domain)}
              >
                {item.marketplace_name ?? item.marketplace_domain}
              </button>
            ))}
          </div>
          <select
            value={priceChangeRange}
            onChange={(event) => setPriceChangeRange(event.target.value as PriceChangeRange)}
            className="h-8 rounded-md border border-input bg-background px-2.5 text-xs"
          >
            <option value="all">{t("market.overview.rangeAll")}</option>
            <option value="up5">{t("market.overview.rangeUp5")}</option>
            <option value="down5">{t("market.overview.rangeDown5")}</option>
            <option value="flat">{t("market.overview.rangeFlat")}</option>
          </select>
        </div>

        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          <button type="button" className={cn("rounded-full border px-2.5 py-0.5 text-xs", historyOnly ? "border-primary text-foreground" : "border-border text-muted-foreground")} onClick={() => setHistoryOnly((value) => !value)}>
            {t("market.overview.historyOnly")}
          </button>
            <button type="button" className="rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground" onClick={() => setPriceChangeRange("up5")}>
            {t("market.overview.quickFilterGt5")}
          </button>
          <button type="button" className="rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground" onClick={() => { setSelectedMarketplaces([]); setPriceChangeRange("all"); setHistoryOnly(false); setSearchRaw(""); }}>
            {t("products.clearFilters")}
          </button>
        </div>

        <div className="mt-3 flex flex-wrap gap-1 border-b border-border pb-2">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={cn("rounded-md px-2.5 py-1 text-xs", activeTab === tab.key ? "bg-primary/12 font-semibold text-foreground" : "text-muted-foreground hover:text-foreground")}
              onClick={() => setActiveTab(tab.key)}
            >
              {t(tab.labelKey)}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="mt-4 space-y-2">
            {Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-12 w-full" />)}
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="mt-4">
            <EmptyState title="dashboard.market.noData" description="market.overview.noDataDescription" icon={AlertTriangle} />
          </div>
        ) : viewMode === "table" ? (
          <div className="mt-4 overflow-auto">
            <Table>
              <TableHeader>
                {table.getHeaderGroups().map((headerGroup) => (
                  <TableRow key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <TableHead key={header.id}>
                        {header.isPlaceholder ? null : (
                          <button
                            type="button"
                            className="text-left text-xs uppercase tracking-wide text-muted-foreground"
                            onClick={header.column.getToggleSortingHandler()}
                          >
                            {flexRender(header.column.columnDef.header, header.getContext())}
                          </button>
                        )}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {table.getRowModel().rows.slice(0, visibleCount).map((row) => (
                  <TableRow key={row.id}>
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visibleItems.map((item) => (
              <article key={item.id} className="rounded-xl border border-border bg-background p-4">
                <div className="flex items-start gap-3">
                  <div className="scale-150 origin-top-left">
                    <ProductThumb item={item} />
                  </div>
                  <div className="min-w-0">
                    <p className="line-clamp-2 text-sm font-semibold">{item.title ?? t("market.overview.untitled")}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.marketplace_name ?? item.marketplace_domain ?? t("dashboard.market.marketplace")}
                    </p>
                    <p className="mt-2 font-mono">{formatPrice(item.current_price, item.currency, locale)}</p>
                    <p className={cn("text-xs", (item.price_change_pct_24h ?? 0) >= 0 ? "text-[var(--color-price-down)]" : "text-[var(--color-price-up)]")}>{formatPercent(item.price_change_pct_24h)}</p>
                  </div>
                </div>
                <Sparkline className="mt-3" points={(item.recent_prices ?? []).map((point) => ({ date: point.date, price: point.price }))} />
                <div className="mt-4 flex items-center justify-between gap-2">
                  <Button size="sm" asChild>
                    <Link to={`/products/${item.product_id ?? item.id}`}>{t("market.overview.details")}</Link>
                  </Button>
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" disabled={item.current_price == null || !item.currency} onClick={() => addProductMutation.mutate(item)}>
                      {t("market.overview.addToMyProducts")}
                    </Button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
        {filteredItems.length > MARKET_OVERVIEW_INITIAL_VISIBLE ? (
          <div className="mt-4 flex items-center justify-center gap-2">
            {hasMoreItems ? (
              <Button
                variant="outline"
                onClick={() => {
                  setVisibleCount((prev) => Math.min(filteredItems.length, prev + MARKET_OVERVIEW_EXPAND_STEP));
                }}
              >
                {t("market.overview.expandBy", { count: MARKET_OVERVIEW_EXPAND_STEP })}
              </Button>
            ) : null}
            {canCollapse ? (
              <Button
                variant="ghost"
                onClick={() => setVisibleCount(MARKET_OVERVIEW_INITIAL_VISIBLE)}
              >
                {t("market.overview.collapse")}
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
