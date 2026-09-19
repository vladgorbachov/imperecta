/**
 * Query client + offline snapshot persistence (stale-while-revalidate,
 * 2026-09-19).
 *
 * Three cache layers stack up for the public storefront reads:
 *   1. this persisted client — a returning visitor paints the last page
 *      they saw straight from localStorage, no network round-trip;
 *   2. the CDN in front of api./data.imperecta.com — 5-minute snapshots
 *      shared by every viewer (Cache-Control: public, s-maxage=300);
 *   3. the origin's own materialized views / in-memory search index.
 * After the instant paint the pool grid catches up to live prices via
 * usePoolProducts' refresh loop. Only whitelisted public queries persist;
 * anything user-scoped (alerts, preferences, admin) stays memory-only.
 *
 * Persistence is built on react-query's own dehydrate/hydrate (no extra
 * packages): restore once at startup, then write a throttled snapshot on
 * every cache change.
 */

import { QueryClient, dehydrate, hydrate, type DehydratedState } from "@tanstack/react-query";

/** Top-level query keys whose data is public and safe to keep on disk. */
const PERSISTED_ROOT_KEYS = new Set<string>([
  "pool-products",
  "pool-categories",
  "pool-product-detail",
  "pool-price-history",
  "listing-comparison",
  "news",
]);

/** ["markets", <sub>, ...] — public sub-keys only (preferences/instruments
    are per-user and stay memory-only). */
const PERSISTED_MARKETS_SUBKEYS = new Set<string>([
  "pool-marketplace-stats",
  "kpi-history",
  "volatility",
  "pool-stats",
  "dashboard-kpi",
  "geo-coverage",
  "trend",
  "movements",
]);

export function isPersistedQueryKey(queryKey: readonly unknown[]): boolean {
  const [head, sub] = queryKey;
  if (typeof head !== "string") return false;
  if (head === "markets") return typeof sub === "string" && PERSISTED_MARKETS_SUBKEYS.has(sub);
  return PERSISTED_ROOT_KEYS.has(head);
}

/** Bump when the shape of a persisted payload changes incompatibly. */
export const PERSIST_BUSTER = "swr-v1";
export const PERSIST_STORAGE_KEY = "imperecta-query-snapshot";

/** Snapshots older than this are dropped on restore (ms). */
export const PERSIST_MAX_AGE = 24 * 60 * 60 * 1000;

const PERSIST_THROTTLE_MS = 1_000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      /* Public reads are 5-minute snapshots by contract; user-scoped hooks
         override with their own staleTime. */
      staleTime: 60_000,
      gcTime: PERSIST_MAX_AGE,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

interface PersistedSnapshot {
  buster: string;
  timestamp: number;
  state: DehydratedState;
}

function storageOrNull(): Storage | null {
  try {
    if (typeof window === "undefined") return null;
    const probe = "__imperecta_persist_probe__";
    window.localStorage.setItem(probe, "1");
    window.localStorage.removeItem(probe);
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Restore a previous snapshot into `client`; returns whether one applied. */
export function restoreSnapshot(
  client: QueryClient,
  storage: Pick<Storage, "getItem" | "removeItem">,
  now: number = Date.now(),
): boolean {
  try {
    const raw = storage.getItem(PERSIST_STORAGE_KEY);
    if (!raw) return false;
    const snapshot = JSON.parse(raw) as PersistedSnapshot;
    if (snapshot.buster !== PERSIST_BUSTER || now - snapshot.timestamp > PERSIST_MAX_AGE) {
      storage.removeItem(PERSIST_STORAGE_KEY);
      return false;
    }
    hydrate(client, snapshot.state);
    return true;
  } catch {
    try {
      storage.removeItem(PERSIST_STORAGE_KEY);
    } catch {
      /* storage may be read-only; nothing to clean */
    }
    return false;
  }
}

/** Serialize the whitelisted successful queries of `client`. */
export function buildSnapshot(client: QueryClient, now: number = Date.now()): PersistedSnapshot {
  return {
    buster: PERSIST_BUSTER,
    timestamp: now,
    state: dehydrate(client, {
      shouldDehydrateQuery: (query) =>
        query.state.status === "success" && isPersistedQueryKey(query.queryKey),
    }),
  };
}

/**
 * Wire persistence for `client`: restore once, then write a throttled
 * snapshot on every cache change. Returns an unsubscribe function.
 */
export function setupQueryPersistence(
  client: QueryClient,
  storage: Storage | null = storageOrNull(),
): () => void {
  if (!storage) return () => undefined;
  restoreSnapshot(client, storage);

  let timer: number | null = null;
  const flush = () => {
    timer = null;
    try {
      storage.setItem(PERSIST_STORAGE_KEY, JSON.stringify(buildSnapshot(client)));
    } catch {
      /* quota exceeded or private mode: the in-memory cache still works */
    }
  };
  const unsubscribe = client.getQueryCache().subscribe(() => {
    if (timer !== null) return;
    timer = window.setTimeout(flush, PERSIST_THROTTLE_MS);
  });
  return () => {
    unsubscribe();
    if (timer !== null) window.clearTimeout(timer);
  };
}
