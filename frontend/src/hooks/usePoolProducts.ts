import { useEffect, useRef } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import type { PoolProductItem, PoolProductsParams, PoolProductsResponse } from "@/api/products";
import { productsApi } from "@/api/products";
import { dataOpsApi } from "@/api/dataOps";
import { useDisplayCurrencyStore } from "@/stores/displayCurrencyStore";

/**
 * Snapshot-then-refresh (2026-09-19): the grid renders instantly from the
 * persisted query cache / the CDN's 5-minute snapshot, then asks data-ops
 * for the CURRENT rows of exactly the ids on screen and swaps them in —
 * once right after the page arrives, then every LIVE_REFRESH_MS while the
 * tab is visible. The refresh is a PK lookup on <= 500 ids, never cached.
 */
export const LIVE_REFRESH_MS = 150_000;

/** Pool pages stay fresh for 5 minutes (the CDN snapshot window). */
export const POOL_STALE_MS = 5 * 60_000;

export function mergeRefreshedItems(
  page: PoolProductsResponse,
  fresh: PoolProductItem[],
): PoolProductsResponse {
  if (fresh.length === 0) return page;
  const byId = new Map(fresh.map((item) => [item.id, item]));
  let changed = false;
  const items = page.items.map((item) => {
    const next = byId.get(item.id);
    if (!next) return item;
    changed = true;
    /* Keep the snapshot's sparkline when the refresh returns none. */
    const recent = next.recent_prices?.length ? next.recent_prices : item.recent_prices;
    return { ...item, ...next, recent_prices: recent };
  });
  return changed ? { ...page, items } : page;
}

export function usePoolProducts(
  params: PoolProductsParams,
  options?: { enabled?: boolean; liveRefresh?: boolean },
) {
  const displayCurrency = useDisplayCurrencyStore((state) => state.displayCurrency);
  const requestParams = { ...params, display_currency: displayCurrency };
  const queryClient = useQueryClient();
  const queryKey = ["pool-products", requestParams] as const;

  const query = useQuery({
    queryKey,
    queryFn: async () => {
      const { data } = await productsApi.fetchPoolProducts(requestParams);
      return data;
    },
    staleTime: POOL_STALE_MS,
    /* Page flips render instantly over the previous page instead of a
       skeleton — perceived latency win while the next page loads. */
    placeholderData: keepPreviousData,
    enabled: options?.enabled ?? true,
  });

  const liveRefresh = options?.liveRefresh ?? true;
  const pageIds = query.data?.items.map((item) => item.id).join(",") ?? "";
  const inFlight = useRef(false);

  useEffect(() => {
    if (!liveRefresh || !pageIds) return;
    const ids = pageIds.split(",");
    let cancelled = false;

    const catchUp = async () => {
      if (inFlight.current || document.visibilityState === "hidden") return;
      inFlight.current = true;
      try {
        const { data } = await dataOpsApi.refreshPoolProducts(ids, displayCurrency);
        if (cancelled) return;
        queryClient.setQueryData<PoolProductsResponse>(queryKey, (page) =>
          page ? mergeRefreshedItems(page, data.items) : page,
        );
      } catch {
        /* Live catch-up is best-effort: the snapshot stays on screen. */
      } finally {
        inFlight.current = false;
      }
    };

    void catchUp();
    const timer = window.setInterval(() => void catchUp(), LIVE_REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
    // queryKey is derived from pageIds + displayCurrency; ids drive the effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageIds, displayCurrency, liveRefresh, queryClient]);

  return query;
}

export function usePoolCategories() {
  return useQuery({
    queryKey: ["pool-categories"],
    queryFn: async () => {
      const { data } = await productsApi.getPoolCategories();
      return data;
    },
    staleTime: POOL_STALE_MS,
  });
}
