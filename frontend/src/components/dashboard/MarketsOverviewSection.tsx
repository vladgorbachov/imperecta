import { useMemo, useState } from "react";
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
import { AlertTriangle, BellPlus, Grid3X3, List, Plus, Search } from "lucide-react";
import { toast } from "sonner";
import { alertsApi } from "@/api/alerts";
import { marketsApi, marketsQueryKeys, type MarketsOverviewItem } from "@/api/markets";
import { productsApi } from "@/api/products";
import { Sparkline } from "@/components/ui-custom/Sparkline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDebounce } from "@/hooks/useDebounce";
import { cn } from "@/lib/utils";

type MarketsTab = "volatile" | "trending" | "gainers" | "losers" | "recent";
type ViewMode = "table" | "cards";
type PriceChangeRange = "all" | "up5" | "down5" | "flat";

const PAGE_LIMIT = 200;

const TABS: Array<{ key: MarketsTab; label: string }> = [
  { key: "volatile", label: "Волатильные" },
  { key: "trending", label: "Трендовые" },
  { key: "gainers", label: "Растут" },
  { key: "losers", label: "Падают" },
  { key: "recent", label: "Недавние" },
];

function formatPrice(value?: number | null, currency?: string | null): string {
  if (value == null) {
    return "—";
  }
  const formatted = new Intl.NumberFormat("ru-RU", {
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
    return <img src={item.image_url} alt={item.title ?? "Товар"} className="size-10 rounded-md object-cover" loading="lazy" />;
  }
  return (
    <div className="flex size-10 items-center justify-center rounded-md border border-border text-xs text-muted-foreground">
      {(item.title ?? "?").slice(0, 1).toUpperCase()}
    </div>
  );
}

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-[var(--glass-bg)] p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 text-xl font-semibold">{value}</p>
    </div>
  );
}

export function MarketsOverviewSection() {
  const [activeTab, setActiveTab] = useState<MarketsTab>("volatile");
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [searchRaw, setSearchRaw] = useState("");
  const [sorting, setSorting] = useState<SortingState>([{ id: "price_change_pct_24h", desc: true }]);
  const [selectedMarketplaces, setSelectedMarketplaces] = useState<string[]>([]);
  const [priceChangeRange, setPriceChangeRange] = useState<PriceChangeRange>("all");
  const [historyOnly, setHistoryOnly] = useState(false);
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

  const createAlertMutation = useMutation({
    mutationFn: (productId?: string | null) => alertsApi.create({ product_id: productId ?? undefined, type: "price_drop", threshold_percent: 5, channel: "email" }),
    onSuccess: () => toast.success("Алерт создан"),
    onError: () => toast.error("Не удалось создать алерт"),
  });
  const addProductMutation = useMutation({
    mutationFn: (item: MarketsOverviewItem) => {
      if (item.current_price == null || !item.currency) {
        throw new Error("Missing price data");
      }
      return productsApi.create({
        name: item.title ?? "Товар из рынка",
        current_price: item.current_price,
        currency: item.currency,
        url: item.url,
      });
    },
    onSuccess: () => toast.success("Товар добавлен в Мои товары"),
    onError: () => toast.error("Не удалось добавить товар"),
  });

  const rawItems = data?.items ?? [];
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
      lastUpdate: lastUpdate ? new Date(lastUpdate).toLocaleString("ru-RU") : "—",
    };
  }, [data?.total, filteredItems, poolStats?.total_products]);

  const columnHelper = createColumnHelper<MarketsOverviewItem>();
  const columns = useMemo(
    () => [
      columnHelper.display({
        id: "image",
        header: "Изображение",
        cell: ({ row }) => <ProductThumb item={row.original} />,
      }),
      columnHelper.accessor((row) => row.title ?? "", {
        id: "title",
        header: "Название товара",
        cell: ({ row }) => <span className="line-clamp-2 font-medium">{row.original.title ?? "Без названия"}</span>,
      }),
      columnHelper.accessor((row) => row.marketplace_name ?? row.marketplace_domain ?? "Маркетплейс", {
        id: "marketplace",
        header: "Маркетплейс",
        cell: ({ getValue }) => <Badge variant="outline">{getValue()}</Badge>,
      }),
      columnHelper.accessor((row) => row.current_price ?? null, {
        id: "current_price",
        header: "Текущая цена",
        cell: ({ row }) => <span className="font-mono">{formatPrice(row.original.current_price, row.original.currency)}</span>,
      }),
      columnHelper.accessor((row) => row.price_change_pct_24h ?? null, {
        id: "price_change_pct_24h",
        header: "Изменение (24ч)",
        cell: ({ row }) => (
          <span className={cn("font-mono", (row.original.price_change_pct_24h ?? 0) > 0 && "text-[var(--color-price-down)]", (row.original.price_change_pct_24h ?? 0) < 0 && "text-[var(--color-price-up)]")}>
            {formatPercent(row.original.price_change_pct_24h)}
          </span>
        ),
      }),
      columnHelper.display({
        id: "sparkline",
        header: "Sparkline (7д)",
        cell: ({ row }) => (
          <Sparkline
            className="w-36"
            points={(row.original.recent_prices ?? []).map((point) => ({ date: point.date, price: point.price }))}
          />
        ),
      }),
      columnHelper.accessor((row) => row.last_scraped_at ?? "", {
        id: "last_scraped_at",
        header: "Последнее обновление",
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">
            {row.original.last_scraped_at ? new Date(row.original.last_scraped_at).toLocaleString("ru-RU") : "—"}
          </span>
        ),
      }),
      columnHelper.accessor((row) => row.status, {
        id: "status",
        header: "Статус",
        cell: ({ getValue }) => (
          <Badge variant={getValue() === "active" ? "default" : "secondary"}>
            {getValue() === "active" ? "Активен" : "Неактивен"}
          </Badge>
        ),
      }),
      columnHelper.display({
        id: "actions",
        header: "Действия",
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1">
            <Button size="sm" variant="outline" onClick={() => createAlertMutation.mutate(row.original.product_id)}>
              <BellPlus className="mr-1 size-3.5" />
              Алерт
            </Button>
            <Button size="sm" variant="outline" disabled={row.original.current_price == null || !row.original.currency} onClick={() => addProductMutation.mutate(row.original)}>
              <Plus className="mr-1 size-3.5" />
              В мои
            </Button>
            <Button size="sm" asChild>
              <Link to={`/products/${row.original.product_id ?? row.original.id}`}>История</Link>
            </Button>
          </div>
        ),
      }),
    ],
    [addProductMutation, columnHelper, createAlertMutation],
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
          Не удалось загрузить обзор рынка
        </div>
        <Button onClick={() => refetch()}>Повторить</Button>
      </div>
    );
  }

  return (
    <section className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <KpiCard label="Всего товаров в пуле" value={kpis.total} />
        <KpiCard label="Обновлено за 24ч" value={kpis.updated24h} />
        <KpiCard label="Товаров с изменением >5%" value={kpis.changedMore5} />
        <KpiCard label="Средняя волатильность пула" value={kpis.avgVolatility} />
        <KpiCard label="Последнее обновление" value={kpis.lastUpdate} />
      </div>

      <div className="rounded-xl border border-border bg-[var(--glass-bg)] p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide">Обзор рынка</h3>
          <div className="flex items-center gap-1 rounded-md border border-border p-1">
            <Button size="sm" variant={viewMode === "table" ? "secondary" : "ghost"} onClick={() => setViewMode("table")}>
              <List className="mr-1 size-4" />
              Таблица
            </Button>
            <Button size="sm" variant={viewMode === "cards" ? "secondary" : "ghost"} onClick={() => setViewMode("cards")}>
              <Grid3X3 className="mr-1 size-4" />
              Карточки
            </Button>
          </div>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[1.4fr_1fr_220px]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={searchRaw} onChange={(event) => setSearchRaw(event.target.value)} placeholder="Улучшенный поиск по товарам" className="pl-9" />
          </div>
          <div className="flex flex-wrap gap-2">
            {marketplaceStats.slice(0, 8).map((item) => (
              <button
                key={item.marketplace_domain}
                type="button"
                className={cn("rounded-full border px-3 py-1 text-xs", selectedMarketplaces.includes(item.marketplace_domain) ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground")}
                onClick={() => toggleMarketplace(item.marketplace_domain)}
              >
                {item.marketplace_name ?? item.marketplace_domain}
              </button>
            ))}
          </div>
          <select
            value={priceChangeRange}
            onChange={(event) => setPriceChangeRange(event.target.value as PriceChangeRange)}
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="all">Диапазон изменения: Все</option>
            <option value="up5">Рост больше 5%</option>
            <option value="down5">Падение больше 5%</option>
            <option value="flat">Флэт (-5%..5%)</option>
          </select>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button type="button" className={cn("rounded-full border px-3 py-1 text-xs", historyOnly ? "border-primary text-primary" : "border-border text-muted-foreground")} onClick={() => setHistoryOnly((value) => !value)}>
            Только с историей цен
          </button>
            <button type="button" className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground" onClick={() => setPriceChangeRange("up5")}>
            Быстрый фильтр: {" > "}5%
          </button>
          <button type="button" className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground" onClick={() => { setSelectedMarketplaces([]); setPriceChangeRange("all"); setHistoryOnly(false); setSearchRaw(""); }}>
            Сбросить фильтры
          </button>
        </div>

        <div className="mt-4 flex flex-wrap gap-1 border-b border-border pb-2">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={cn("rounded-md px-3 py-1.5 text-sm", activeTab === tab.key ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground")}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
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
                {table.getRowModel().rows.map((row) => (
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
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {filteredItems.map((item) => (
              <article key={item.id} className="rounded-xl border border-border bg-background p-4">
                <div className="flex items-start gap-3">
                  <div className="scale-150 origin-top-left">
                    <ProductThumb item={item} />
                  </div>
                  <div className="min-w-0">
                    <p className="line-clamp-2 text-sm font-semibold">{item.title ?? "Без названия"}</p>
                    <p className="text-xs text-muted-foreground">{item.marketplace_name ?? item.marketplace_domain ?? "Маркетплейс"}</p>
                    <p className="mt-2 font-mono">{formatPrice(item.current_price, item.currency)}</p>
                    <p className={cn("text-xs", (item.price_change_pct_24h ?? 0) >= 0 ? "text-[var(--color-price-down)]" : "text-[var(--color-price-up)]")}>{formatPercent(item.price_change_pct_24h)}</p>
                  </div>
                </div>
                <Sparkline className="mt-3" points={(item.recent_prices ?? []).map((point) => ({ date: point.date, price: point.price }))} />
                <div className="mt-3 flex flex-wrap gap-1">
                  <Button size="sm" variant="outline" onClick={() => createAlertMutation.mutate(item.product_id)}>
                    Алерт
                  </Button>
                  <Button size="sm" variant="outline" disabled={item.current_price == null || !item.currency} onClick={() => addProductMutation.mutate(item)}>
                    В мои товары
                  </Button>
                  <Button size="sm" asChild>
                    <Link to={`/products/${item.product_id ?? item.id}`}>Детали</Link>
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
