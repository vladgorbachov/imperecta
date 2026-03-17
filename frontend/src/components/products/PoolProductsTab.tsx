/**
 * Displays products from global marketplace pool.
 *
 * Features:
 * - Search by title (debounced 500ms)
 * - Filter by marketplace (dropdown from /api/pool/categories)
 * - Sort: По дате, По алфавиту, По цене, По тренду
 * - Pagination with configurable page size (20/50/100)
 * - Each product row: image, title (clickable), marketplace badge, price, price change
 */

import { useState, useMemo } from "react";
import { Search } from "lucide-react";
import { formatPrice } from "@/lib/formatters";
import { useDebounce } from "@/hooks/useDebounce";
import { usePoolProducts, usePoolCategories } from "@/hooks/usePoolProducts";
import { MarketplaceBadge } from "@/components/ui-custom/MarketplaceBadge";
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
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Package } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PoolProductItem } from "@/api/products";

const PAGE_SIZES = [20, 50, 100] as const;
const SORT_OPTIONS = [
  { value: "recent", label: "По дате" },
  { value: "name_asc", label: "По алфавиту ↑" },
  { value: "name_desc", label: "По алфавиту ↓" },
  { value: "price_asc", label: "По цене ↑" },
  { value: "price_desc", label: "По цене ↓" },
  { value: "trending", label: "По тренду" },
  { value: "gainers", label: "Рост" },
  { value: "losers", label: "Падение" },
  { value: "volatile", label: "Волатильность" },
] as const;

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

export function PoolProductsTab({ locale }: { locale: string }) {
  const [searchRaw, setSearchRaw] = useState("");
  const [marketplaceId, setMarketplaceId] = useState<string>("all");
  const [sort, setSort] = useState<string>("recent");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const search = useDebounce(searchRaw, 500);
  const offset = (page - 1) * pageSize;

  const { data: categories = [] } = usePoolCategories();
  const { data, isLoading } = usePoolProducts({
    search: search.length >= 2 ? search : undefined,
    marketplace_id: marketplaceId !== "all" ? Number(marketplaceId) : undefined,
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
      <div className="glass-card flex flex-col gap-4 rounded-xl p-4 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="relative flex-1 lg:max-w-72">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Поиск по названию"
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
            <SelectValue placeholder="Маркетплейс" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все маркетплейсы</SelectItem>
            {categories.map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                {c.name || c.domain} ({c.product_count})
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
            <SelectValue placeholder="Сортировка" />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="glass-card overflow-hidden rounded-xl">
        {isLoading ? (
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
          <div className="flex flex-col items-center justify-center gap-4 px-4 py-12">
            <p className="text-sm text-muted-foreground">Нет результатов</p>
            <Button
              variant="outline"
              onClick={() => {
                setSearchRaw("");
                setMarketplaceId("all");
                setPage(1);
              }}
            >
              Сбросить фильтры
            </Button>
          </div>
        ) : (
          <div className="max-h-[55vh] overflow-x-auto overflow-y-auto scrollbar-none sm:max-h-[calc(100vh-20rem)]">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-12" />
                  <TableHead>Название</TableHead>
                  <TableHead>Маркетплейс</TableHead>
                  <TableHead>Цена</TableHead>
                  <TableHead>Изменение 24ч</TableHead>
                  <TableHead>Изменение 7д</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow
                    key={item.id}
                    className="cursor-pointer transition-colors hover:bg-muted/50"
                    onClick={() => item.url && window.open(item.url, "_blank")}
                  >
                    <TableCell className="w-12">
                      <ProductThumbnail item={item} />
                    </TableCell>
                    <TableCell>
                      <span className="line-clamp-2 font-medium">
                        {item.title || "—"}
                      </span>
                    </TableCell>
                    <TableCell>
                      <MarketplaceBadge
                        marketplace={item.marketplace_domain || item.marketplace_name || String(item.marketplace_id)}
                        size="sm"
                      />
                    </TableCell>
                    <TableCell>
                      {item.current_price != null
                        ? formatPrice(item.current_price, item.currency || "USD", locale)
                        : "—"}
                    </TableCell>
                    <TableCell>
                      {item.price_change_pct_24h != null ? (
                        <span
                          className={cn(
                            "font-medium",
                            item.price_change_pct_24h > 0 && "text-green-500",
                            item.price_change_pct_24h < 0 && "text-red-500"
                          )}
                        >
                          {item.price_change_pct_24h > 0 ? "+" : ""}
                          {item.price_change_pct_24h.toFixed(2)}%
                        </span>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell>
                      {item.price_change_pct_7d != null ? (
                        <span
                          className={cn(
                            "text-sm",
                            item.price_change_pct_7d > 0 && "text-green-500",
                            item.price_change_pct_7d < 0 && "text-red-500"
                          )}
                        >
                          {item.price_change_pct_7d > 0 ? "+" : ""}
                          {item.price_change_pct_7d.toFixed(2)}%
                        </span>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {!isEmpty && !isLoading && total > 0 && (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">
            Показано {start + 1}–{Math.min(start + pageSize, total)} из {total}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={clampedPage <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Назад
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
              Вперёд
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
