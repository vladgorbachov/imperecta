import { useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { marketsApi, marketsQueryKeys, type MarketsOverviewItem } from "@/api/markets";
import { TrendBadge } from "@/components/ui-custom/TrendBadge";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useDebounce } from "@/hooks/useDebounce";
import { cn } from "@/lib/utils";

type SortTab = "volatile" | "trending" | "gainers" | "losers" | "recent";

const PAGE_LIMIT = 50;

function stringToColor(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i += 1) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const h = Math.abs(hash) % 360;
  return `hsl(${h}, 55%, 45%)`;
}

function ProductThumbnail({ imageUrl, title }: { imageUrl?: string | null; title?: string | null }) {
  const letter = (title?.trim().charAt(0) || "?").toUpperCase();
  const bg = stringToColor(title || "pool");

  if (imageUrl) {
    return (
      <img
        src={imageUrl}
        alt={title || "Изображение товара"}
        className="size-10 rounded-md object-cover"
        loading="lazy"
      />
    );
  }

  return (
    <div
      className="flex size-10 items-center justify-center rounded-md text-sm font-bold text-white"
      style={{ backgroundColor: bg }}
      aria-hidden
    >
      {letter}
    </div>
  );
}

function formatPrice(price?: number | null, currency?: string | null): string {
  if (price == null) {
    return "—";
  }
  const normalizedCurrency = (currency || "USD").toUpperCase();
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency: normalizedCurrency,
      maximumFractionDigits: 2,
    }).format(price);
  } catch {
    return `${price.toFixed(2)} ${normalizedCurrency}`;
  }
}

function formatChange(value?: number | null): string {
  if (value == null) {
    return "—";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function getTrendDirection(value?: number | null): "up" | "down" | "stable" {
  if (value == null || value === 0) {
    return "stable";
  }
  return value > 0 ? "up" : "down";
}

export function MarketDataTable() {
  const [sort, setSort] = useState<SortTab>("volatile");
  const [searchInput, setSearchInput] = useState("");
  const [marketplaceDomain, setMarketplaceDomain] = useState<string>("all");
  const [offset, setOffset] = useState(0);

  const debouncedSearch = useDebounce(searchInput, 500);

  const { data: marketplaceCatalogData } = useQuery({
    queryKey: marketsQueryKeys.overview({ sort: "recent", limit: 200, offset: 0 }),
    queryFn: async () => {
      const { data } = await marketsApi.getOverview({ sort: "recent", limit: 200, offset: 0 });
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });

  const selectedMarketplaceId = useMemo(() => {
    if (marketplaceDomain === "all") {
      return undefined;
    }
    const matched = (marketplaceCatalogData?.items ?? []).find(
      (item) => item.marketplace_domain === marketplaceDomain
    );
    return matched?.marketplace_id;
  }, [marketplaceDomain, marketplaceCatalogData?.items]);

  const overviewParams = useMemo(
    () => ({
      sort,
      search: debouncedSearch || undefined,
      marketplace_id: selectedMarketplaceId,
      limit: PAGE_LIMIT,
      offset,
    }),
    [sort, debouncedSearch, selectedMarketplaceId, offset]
  );

  const { data: overviewData, isLoading } = useQuery({
    queryKey: marketsQueryKeys.overview(overviewParams),
    queryFn: async () => {
      const { data } = await marketsApi.getOverview(overviewParams);
      return data;
    },
    placeholderData: keepPreviousData,
    staleTime: 2 * 60 * 1000,
  });

  const { data: marketplaceStats } = useQuery({
    queryKey: marketsQueryKeys.poolMarketplaceStats(),
    queryFn: async () => {
      const { data } = await marketsApi.getPoolMarketplaceStats();
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });

  const items = overviewData?.items ?? [];
  const total = overviewData?.total ?? 0;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_LIMIT < total;

  const tabs: { key: SortTab; label: string }[] = [
    { key: "volatile", label: "Волатильные" },
    { key: "trending", label: "Трендовые" },
    { key: "gainers", label: "Растут" },
    { key: "losers", label: "Падают" },
    { key: "recent", label: "Недавние" },
  ];

  return (
    <div className="glass-card flex min-h-[620px] flex-1 flex-col overflow-hidden rounded-xl">
      <h3 className="px-4 pb-2 pt-4 text-sm font-semibold uppercase tracking-wider">Обзор рынка</h3>

      <div className="grid gap-2 px-4 pb-3 sm:grid-cols-[1fr_220px]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchInput}
            onChange={(event) => {
              setSearchInput(event.target.value);
              setOffset(0);
            }}
            placeholder="Поиск товаров"
            className="pl-9"
          />
        </div>

        <select
          value={marketplaceDomain}
          onChange={(event) => {
            setMarketplaceDomain(event.target.value);
            setOffset(0);
          }}
          className="h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">Все маркетплейсы</option>
          {(marketplaceStats ?? []).map((item) => (
            <option key={item.marketplace_domain} value={item.marketplace_domain}>
              {item.marketplace_name || item.marketplace_domain}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap gap-1 border-b px-4" style={{ borderColor: "var(--glass-border)" }}>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => {
              setSort(tab.key);
              setOffset(0);
            }}
            className={cn(
              "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              sort === tab.key ? "text-foreground" : "text-muted-foreground hover:text-foreground"
            )}
            style={sort === tab.key ? { borderColor: "var(--accent)" } : { borderColor: "transparent" }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div
        className="max-h-[510px] flex-1 overflow-auto [&::-webkit-scrollbar]:hidden"
        style={{ scrollbarWidth: "none" }}
      >
        {isLoading ? (
          <div className="space-y-3 px-4 py-8">
            {Array.from({ length: 6 }).map((_, idx) => (
              <Skeleton key={idx} className="h-12 w-full" />
            ))}
          </div>
        ) : total === 0 ? (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-muted-foreground">
            Товары загружаются. Discovery crawler собирает данные с маркетплейсов.
          </div>
        ) : (
          <table className="w-full min-w-[980px]">
            <thead className="sticky top-0 z-10 bg-[var(--background-elevated-subtle)]">
              <tr className="border-b border-border">
                <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-muted-foreground">Товар</th>
                <th className="px-3 py-2 text-left text-xs uppercase tracking-wider text-muted-foreground">Маркетплейс</th>
                <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted-foreground">Цена</th>
                <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted-foreground">24ч</th>
                <th className="px-3 py-2 text-right text-xs uppercase tracking-wider text-muted-foreground">30D</th>
                <th className="px-3 py-2 text-center text-xs uppercase tracking-wider text-muted-foreground">TREND</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row: MarketsOverviewItem) => {
                const change24 = row.price_change_pct_24h;
                const change30 = row.price_change_pct_30d;
                const change7 = row.price_change_pct_7d;
                return (
                  <tr key={row.id} className="border-b border-border/70 hover:bg-[var(--glass-bg-hover)]">
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-3">
                        <ProductThumbnail imageUrl={row.image_url} title={row.title} />
                        <div className="min-w-0">
                          <a
                            href={row.url}
                            target="_blank"
                            rel="noreferrer"
                            className="block truncate text-sm font-medium hover:underline"
                            title={row.title || undefined}
                          >
                            {row.title || "Без названия"}
                          </a>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <Badge variant="outline" className="max-w-[220px] truncate">
                        {row.marketplace_name || row.marketplace_domain || "Маркетплейс"}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-sm">
                      {formatPrice(row.current_price, row.currency)}
                    </td>
                    <td
                      className={cn(
                        "px-3 py-2 text-right font-mono text-sm",
                        (change24 ?? 0) > 0 && "text-green-500",
                        (change24 ?? 0) < 0 && "text-red-500",
                        (change24 ?? 0) === 0 && "text-muted-foreground"
                      )}
                    >
                      {formatChange(change24)}
                    </td>
                    <td
                      className={cn(
                        "px-3 py-2 text-right font-mono text-sm",
                        (change30 ?? 0) > 0 && "text-green-500",
                        (change30 ?? 0) < 0 && "text-red-500",
                        (change30 ?? 0) === 0 && "text-muted-foreground"
                      )}
                    >
                      {formatChange(change30)}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <TrendBadge trend={getTrendDirection(change7)} value={change7 ?? undefined} size="sm" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-border px-4 py-2 text-xs text-muted-foreground">
        <span>Показано {items.length} из {total}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={!canPrev}
            onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_LIMIT))}
            className="rounded-md border border-input px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Назад
          </button>
          <button
            type="button"
            disabled={!canNext}
            onClick={() => setOffset((prev) => prev + PAGE_LIMIT)}
            className="rounded-md border border-input px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Вперёд
          </button>
        </div>
      </div>
    </div>
  );
}
