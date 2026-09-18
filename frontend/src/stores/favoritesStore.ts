/**
 * Client-side product favorites.
 *
 * Stored per browser in localStorage as full item snapshots so the Favorites
 * tab can render without a backend round-trip; a snapshot is refreshed
 * whenever the same listing appears in a fetched pool page. Server-side
 * persistence (cross-device) is documented as P11 in
 * docs/FRONTEND_BACKEND_REQUESTS.md.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { PoolProductItem } from "@/api/products";

export interface FavoriteSnapshot {
  item: PoolProductItem;
  favoritedAt: string;
}

interface FavoritesState {
  favorites: Record<string, FavoriteSnapshot>;
  toggle: (item: PoolProductItem) => void;
  refreshSnapshots: (items: PoolProductItem[]) => void;
}

export const useFavoritesStore = create<FavoritesState>()(
  persist(
    (set, get) => ({
      favorites: {},

      toggle: (item) =>
        set((state) => {
          const next = { ...state.favorites };
          if (next[item.id]) {
            delete next[item.id];
          } else {
            next[item.id] = { item, favoritedAt: new Date().toISOString() };
          }
          return { favorites: next };
        }),

      /** Keep stored snapshots fresh with the latest fetched pool data. */
      refreshSnapshots: (items) => {
        const { favorites } = get();
        let changed = false;
        const next = { ...favorites };
        for (const item of items) {
          const existing = next[item.id];
          if (existing && existing.item !== item) {
            next[item.id] = { ...existing, item };
            changed = true;
          }
        }
        if (changed) {
          set({ favorites: next });
        }
      },
    }),
    { name: "imperecta_favorites" },
  ),
);

export const useIsFavorite = (id: string) =>
  useFavoritesStore((state) => Boolean(state.favorites[id]));
