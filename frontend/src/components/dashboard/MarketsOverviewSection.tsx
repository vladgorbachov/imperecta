import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronDown,
  ExternalLink,
  Plus,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { toast } from "sonner";
import { marketsApi, marketsQueryKeys, type MarketsOverviewItem } from "@/api/markets";
import { productsApi } from "@/api/products";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { DisplayCurrencySelector } from "@/components/ui/DisplayCurrencySelector";
import { PriceDisplay } from "@/components/ui-custom/PriceDisplay";
import { useDebounce } from "@/hooks/useDebounce";
import { useDisplayCurrency } from "@/hooks/useDisplayCurrency";
import { cn } from "@/lib/utils";

type SortKey = "random" | "recent" | "gainers" | "losers" | "volatile" | "trending";

const PAGE_LIMIT = 200;
const MARKET_OVERVIEW_INITIAL_VISIBLE = 20;
const MARKET_OVERVIEW_EXPAND_STEP = 20;

/** Sort keys backed by the /markets/overview endpoint. "random" maps to "recent". */
const SORT_OPTIONS: Array<{ key: SortKey; labelKey: string }> = [
  { key: "random", labelKey: "market.sort.random" },
  { key: "recent", labelKey: "dashboard.market.recentlyUpdated" },
  { key: "gainers", labelKey: "dashboard.market.topGainers" },
  { key: "losers", labelKey: "dashboard.market.topLosers" },
  { key: "volatile", labelKey: "dashboard.market.mostVolatile" },
  { key: "trending", labelKey: "dashboard.market.trendingNow" },
];

function toBackendSort(sort: SortKey): string {
  return sort === "random" ? "recent" : sort;
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

/** Stable pseudo-random rank for a listing id, seeded once per session. */
function seededRank(id: string, seed: number): number {
  let hash = seed >>> 0;
  for (let index = 0; index < id.length; index += 1) {
    hash = Math.imul(hash ^ id.charCodeAt(index), 0x01000193) >>> 0;
  }
  return hash;
}

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-[var(--glass-bg)] p-3">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  );
}

function FilterSection({
  title,
  defaultOpen = true,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <Collapsible defaultOpen={defaultOpen} className="border-b border-border pb-3">
      <CollapsibleTrigger className="group flex w-full items-center justify-between py-2 text-xs font-semibold uppercase tracking-wide text-foreground">
        {title}
        <ChevronDown className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-2 pt-1">{children}</CollapsibleContent>
    </Collapsible>
  );
}

function ProductImage({ item }: { item: MarketsOverviewItem }) {
  if (item.image_url) {
    return (
      <img
        src={item.image_url}
        alt={item.title ?? ""}
        loading="lazy"
        className="h-full w-full object-contain"
      />
    );
  }
  return (
    <div className="flex h-full w-full items-center justify-center text-2xl font-semibold text-muted-foreground">
      {(item.title ?? "?").slice(0, 1).toUpperCase()}
    </div>
  );
}

function ProductCard({
  item,
  onAdd,
  addDisabled,
}: {
  item: MarketsOverviewItem;
  onAdd: (item: MarketsOverviewItem) => void;
  addDisabled: boolean;
}) {
  const { t } = useTranslation();
  const externalHref = item.url || undefined;
  const internalHref = `/products/${item.product_id ?? item.id}`;
  const changeValue = item.price_change_pct_24h ?? null;

  const imageContent = (
    <div className="aspect-square w-full overflow-hidden rounded-lg bg-[var(--background-elevated)]">
      <ProductImage item={item} />
    </div>
  );
  const titleContent = (
    <p className="line-clamp-2 min-h-[2.5rem] text-sm font-medium text-foreground">
      {item.title ?? t("market.overview.untitled")}
    </p>
  );

  return (
    <article className="flex flex-col gap-2 rounded-xl border border-border bg-[var(--glass-bg)] p-3 transition-colors hover:border-[var(--glass-border-hover)]">
      {externalHref ? (
        <a
          href={externalHref}
          target="_blank"
          rel="noopener noreferrer"
          className="space-y-2"
          aria-label={t("market.openProduct")}
        >
          {imageContent}
          {titleContent}
        </a>
      ) : (
        <Link to={internalHref} className="space-y-2">
          {imageContent}
          {titleContent}
        </Link>
      )}

      <div className="mt-auto space-y-1.5">
        <PriceDisplay
          className="text-lg font-bold text-foreground"
          localAmount={item.current_price}
          localCurrency={item.currency}
          displayAmount={item.display_price}
          displayCurrency={item.display_currency}
          conversionAvailable={item.conversion_available}
        />
        <div className="flex items-center justify-between gap-2">
          <Badge variant="outline" className="max-w-[60%] truncate text-[10px]">
            {item.marketplace_name ?? item.marketplace_domain ?? t("dashboard.market.marketplace")}
          </Badge>
          {changeValue != null && (
            <span
              className={cn(
                "text-xs font-medium",
                changeValue > 0 && "text-[var(--color-price-up)]",
                changeValue < 0 && "text-[var(--color-price-down)]",
              )}
            >
              {formatPercent(changeValue)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 pt-1">
          <Button
            size="sm"
            variant="outline"
            className="flex-1"
            disabled={addDisabled}
            onClick={() => onAdd(item)}
          >
            <Plus className="size-3.5" />
            {t("market.overview.addToMyProducts")}
          </Button>
          <Button size="sm" variant="ghost" asChild>
            <Link to={internalHref} aria-label={t("market.overview.details")}>
              <ExternalLink className="size-3.5" />
            </Link>
          </Button>
        </div>
      </div>
    </article>
  );
}

export function MarketsOverviewSection() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const { apiParam: displayCurrency } = useDisplayCurrency();

  const [searchRaw, setSearchRaw] = useState("");
  const [marketplaceSearch, setMarketplaceSearch] = useState("");
  const [selectedMarketplaces, setSelectedMarketplaces] = useState<string[]>([]);
  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const [historyOnly, setHistoryOnly] = useState(false);
  const [sort, setSort] = useState<SortKey>("random");
  const [visibleCount, setVisibleCount] = useState(MARKET_OVERVIEW_INITIAL_VISIBLE);
  const [filtersOpenMobile, setFiltersOpenMobile] = useState(false);
  const debouncedSearch = useDebounce(searchRaw, 400);

  // Random order seed: stable for the session so cards don't reshuffle on re-render.
  const shuffleSeed = useRef<number>(Math.floor(Math.random() * 0x7fffffff) + 1);

  const overviewParams = useMemo(
    () => ({
      sort: toBackendSort(sort),
      limit: PAGE_LIMIT,
      offset: 0,
      search: debouncedSearch.length >= 2 ? debouncedSearch : undefined,
      display_currency: displayCurrency,
    }),
    [sort, debouncedSearch, displayCurrency],
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

  const orderedItems = useMemo(() => {
    if (sort !== "random") {
      return rawItems;
    }
    const seed = shuffleSeed.current;
    return [...rawItems].sort(
      (a, b) => seededRank(a.id, seed) - seededRank(b.id, seed),
    );
  }, [rawItems, sort]);

  const filteredItems = useMemo(() => {
    const min = priceMin.trim() === "" ? null : Number(priceMin);
    const max = priceMax.trim() === "" ? null : Number(priceMax);
    return orderedItems.filter((item) => {
      const inMarketplace =
        selectedMarketplaces.length === 0 ||
        selectedMarketplaces.includes(item.marketplace_domain ?? "");
      if (!inMarketplace) {
        return false;
      }
      if (historyOnly && (item.recent_prices?.length ?? 0) < 2) {
        return false;
      }
      const price = item.current_price;
      if (min != null && !Number.isNaN(min) && (price == null || price < min)) {
        return false;
      }
      if (max != null && !Number.isNaN(max) && (price == null || price > max)) {
        return false;
      }
      return true;
    });
  }, [orderedItems, selectedMarketplaces, historyOnly, priceMin, priceMax]);

  const kpis = useMemo(() => {
    const now = Date.now();
    const updated24h = filteredItems.filter(
      (item) => now - parseDateValue(item.last_scraped_at) <= 24 * 60 * 60 * 1000,
    ).length;
    const changedMore5 = filteredItems.filter(
      (item) => Math.abs(item.price_change_pct_24h ?? 0) > 5,
    ).length;
    const averageVolatility =
      filteredItems.length === 0
        ? 0
        : filteredItems.reduce(
            (acc, item) => acc + Math.abs(item.price_change_pct_24h ?? 0),
            0,
          ) / filteredItems.length;
    const lastUpdate = filteredItems.reduce(
      (max, item) => Math.max(max, parseDateValue(item.last_scraped_at)),
      0,
    );
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
  }, [debouncedSearch, historyOnly, priceMin, priceMax, selectedMarketplaces, sort]);

  const visibleItems = useMemo(
    () => filteredItems.slice(0, visibleCount),
    [filteredItems, visibleCount],
  );
  const hasMoreItems = visibleCount < filteredItems.length;
  const canCollapse =
    filteredItems.length > MARKET_OVERVIEW_INITIAL_VISIBLE &&
    visibleCount > MARKET_OVERVIEW_INITIAL_VISIBLE;

  const localCurrencyUnavailable = useMemo(() => {
    if (selectedMarketplaces.length !== 1) {
      return false;
    }
    const target = selectedMarketplaces[0];
    const item = rawItems.find(
      (candidate) => candidate.marketplace_domain === target,
    );
    if (!item) {
      return false;
    }
    if (item.local_currency_unavailable === true) {
      return true;
    }
    return item.local_currency_resolution?.source === "unknown";
  }, [selectedMarketplaces, rawItems]);

  const visibleMarketplaces = useMemo(() => {
    const query = marketplaceSearch.trim().toLowerCase();
    if (!query) {
      return marketplaceStats;
    }
    return marketplaceStats.filter((item) =>
      `${item.marketplace_name ?? ""} ${item.marketplace_domain}`
        .toLowerCase()
        .includes(query),
    );
  }, [marketplaceStats, marketplaceSearch]);

  const hasActiveFilters =
    selectedMarketplaces.length > 0 ||
    priceMin !== "" ||
    priceMax !== "" ||
    historyOnly ||
    searchRaw !== "";

  const toggleMarketplace = (domain: string) => {
    setSelectedMarketplaces((prev) =>
      prev.includes(domain) ? prev.filter((value) => value !== domain) : [...prev, domain],
    );
  };

  const clearFilters = () => {
    setSelectedMarketplaces([]);
    setPriceMin("");
    setPriceMax("");
    setHistoryOnly(false);
    setSearchRaw("");
    setMarketplaceSearch("");
  };

  const filterPanel = (
    <div className="space-y-3">
      <FilterSection title={t("displayCurrency.label")}>
        <DisplayCurrencySelector
          compact={false}
          className="w-full"
          localUnavailable={localCurrencyUnavailable}
        />
      </FilterSection>

      <FilterSection title={t("market.filters.marketplaces")}>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={marketplaceSearch}
            onChange={(event) => setMarketplaceSearch(event.target.value)}
            placeholder={t("common.search")}
            className="h-8 pl-8 text-xs"
          />
        </div>
        <div className="max-h-56 space-y-1 overflow-auto pr-1">
          {visibleMarketplaces.map((item) => {
            const checked = selectedMarketplaces.includes(item.marketplace_domain);
            return (
              <label
                key={item.marketplace_domain}
                className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-1 text-xs hover:bg-[var(--glass-bg-hover)]"
              >
                <Checkbox
                  checked={checked}
                  onCheckedChange={() => toggleMarketplace(item.marketplace_domain)}
                />
                <span className="min-w-0 flex-1 truncate text-foreground">
                  {item.marketplace_name ?? item.marketplace_domain}
                </span>
                <span className="shrink-0 text-muted-foreground">{item.product_count}</span>
              </label>
            );
          })}
        </div>
      </FilterSection>

      <FilterSection title={t("market.filters.price")}>
        <div className="flex items-center gap-2">
          <Input
            type="number"
            inputMode="decimal"
            value={priceMin}
            onChange={(event) => setPriceMin(event.target.value)}
            placeholder={t("market.filters.from")}
            className="h-8 text-xs"
          />
          <span className="text-muted-foreground">—</span>
          <Input
            type="number"
            inputMode="decimal"
            value={priceMax}
            onChange={(event) => setPriceMax(event.target.value)}
            placeholder={t("market.filters.to")}
            className="h-8 text-xs"
          />
        </div>
      </FilterSection>

      <FilterSection title={t("market.filters.options")}>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-foreground">
          <Checkbox
            checked={historyOnly}
            onCheckedChange={(value) => setHistoryOnly(value === true)}
          />
          {t("market.overview.historyOnly")}
        </label>
      </FilterSection>

      {hasActiveFilters && (
        <Button variant="outline" size="sm" className="w-full" onClick={clearFilters}>
          {t("products.clearFilters")}
        </Button>
      )}
    </div>
  );

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

      <div className="grid gap-3 lg:grid-cols-[260px_1fr]">
        <aside className="hidden lg:block">
          <div className="liquid-glass sticky top-2.5 rounded-xl border border-border bg-[var(--glass-bg)] p-3.5">
            <div className="relative mb-3">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={searchRaw}
                onChange={(event) => setSearchRaw(event.target.value)}
                placeholder={t("market.overview.searchPlaceholder")}
                className="pl-9"
              />
            </div>
            {filterPanel}
          </div>
        </aside>

        <div className="min-w-0">
          <div className="liquid-glass rounded-xl border border-border bg-[var(--glass-bg)] p-3.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">
                {t("market.found", { count: Number(kpis.total) })}
              </h3>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="lg:hidden"
                  onClick={() => setFiltersOpenMobile((value) => !value)}
                >
                  <SlidersHorizontal className="size-4" />
                  {t("market.filters.title")}
                </Button>
                <span className="hidden text-xs text-muted-foreground sm:inline">
                  {t("market.sort.label")}
                </span>
                <Select value={sort} onValueChange={(value) => setSort(value as SortKey)}>
                  <SelectTrigger className="h-8 w-[170px] text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent align="end">
                    {SORT_OPTIONS.map((option) => (
                      <SelectItem key={option.key} value={option.key}>
                        {t(option.labelKey)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {filtersOpenMobile && (
              <div className="mt-3 lg:hidden">
                <div className="relative mb-3">
                  <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={searchRaw}
                    onChange={(event) => setSearchRaw(event.target.value)}
                    placeholder={t("market.overview.searchPlaceholder")}
                    className="pl-9"
                  />
                </div>
                {filterPanel}
              </div>
            )}

            {isLoading ? (
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                {Array.from({ length: 10 }).map((_, index) => (
                  <Skeleton key={index} className="h-64 w-full rounded-xl" />
                ))}
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="mt-4">
                <EmptyState
                  title="dashboard.market.noData"
                  description="market.overview.noDataDescription"
                  icon={AlertTriangle}
                />
              </div>
            ) : (
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                {visibleItems.map((item) => (
                  <ProductCard
                    key={item.id}
                    item={item}
                    onAdd={(value) => addProductMutation.mutate(value)}
                    addDisabled={item.current_price == null || !item.currency}
                  />
                ))}
              </div>
            )}

            {filteredItems.length > MARKET_OVERVIEW_INITIAL_VISIBLE ? (
              <div className="mt-4 flex items-center justify-center gap-2">
                {hasMoreItems ? (
                  <Button
                    variant="outline"
                    onClick={() =>
                      setVisibleCount((prev) =>
                        Math.min(filteredItems.length, prev + MARKET_OVERVIEW_EXPAND_STEP),
                      )
                    }
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
        </div>
      </div>
    </section>
  );
}
