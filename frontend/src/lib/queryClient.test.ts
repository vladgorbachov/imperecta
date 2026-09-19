import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import {
  PERSIST_BUSTER,
  PERSIST_MAX_AGE,
  PERSIST_STORAGE_KEY,
  buildSnapshot,
  isPersistedQueryKey,
  restoreSnapshot,
} from "./queryClient";

function memoryStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (k) => map.get(k) ?? null,
    key: (i) => [...map.keys()][i] ?? null,
    removeItem: (k) => void map.delete(k),
    setItem: (k, v) => void map.set(k, v),
  };
}

describe("isPersistedQueryKey", () => {
  it("keeps public reads and drops user-scoped ones", () => {
    expect(isPersistedQueryKey(["pool-products", { sort: "recent" }])).toBe(true);
    expect(isPersistedQueryKey(["markets", "pool-stats"])).toBe(true);
    expect(isPersistedQueryKey(["markets", "preferences"])).toBe(false);
    expect(isPersistedQueryKey(["admin", "marketplaces"])).toBe(false);
    expect(isPersistedQueryKey(["user", "me"])).toBe(false);
    expect(isPersistedQueryKey([{ weird: true }])).toBe(false);
  });
});

describe("snapshot persistence", () => {
  it("round-trips whitelisted successful queries only", () => {
    const client = new QueryClient();
    client.setQueryData(["pool-products", { limit: 1 }], { items: [{ id: "a" }], total: 1 });
    client.setQueryData(["markets", "preferences"], { secret: true });
    const storage = memoryStorage();
    storage.setItem(PERSIST_STORAGE_KEY, JSON.stringify(buildSnapshot(client)));

    const fresh = new QueryClient();
    expect(restoreSnapshot(fresh, storage)).toBe(true);
    expect(fresh.getQueryData(["pool-products", { limit: 1 }])).toEqual({
      items: [{ id: "a" }],
      total: 1,
    });
    expect(fresh.getQueryData(["markets", "preferences"])).toBeUndefined();
  });

  it("drops snapshots that are stale or from another buster", () => {
    const client = new QueryClient();
    client.setQueryData(["pool-categories"], [{ marketplace_id: "m" }]);
    const storage = memoryStorage();

    const old = buildSnapshot(client, Date.now() - PERSIST_MAX_AGE - 1);
    storage.setItem(PERSIST_STORAGE_KEY, JSON.stringify(old));
    expect(restoreSnapshot(new QueryClient(), storage)).toBe(false);
    expect(storage.getItem(PERSIST_STORAGE_KEY)).toBeNull();

    const foreign = { ...buildSnapshot(client), buster: `${PERSIST_BUSTER}-other` };
    storage.setItem(PERSIST_STORAGE_KEY, JSON.stringify(foreign));
    expect(restoreSnapshot(new QueryClient(), storage)).toBe(false);

    storage.setItem(PERSIST_STORAGE_KEY, "{not json");
    expect(restoreSnapshot(new QueryClient(), storage)).toBe(false);
  });
});
