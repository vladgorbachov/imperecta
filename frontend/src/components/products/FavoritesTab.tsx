/**
 * Favorites tab — the user's starred products, rendered from local
 * snapshots (see favoritesStore). Snapshots refresh whenever the same
 * listing appears in a fetched pool page; row click opens the Product Peek
 * which always refetches live detail by id.
 */

import { useMemo, useState } from "react";

import { Star } from "lucide-react";
import type { PoolProductItem } from "@/api/products";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { ProductPeek } from "@/components/products/ProductPeek";
import { ProductRow, ProductsTableHead } from "@/components/products/ProductRow";
import { Scrollable } from "@/components/ui/Scrollable";
import { Table, TableBody } from "@/components/ui/table";
import { useFavoritesStore } from "@/stores/favoritesStore";

export function FavoritesTab() {

  const favorites = useFavoritesStore((state) => state.favorites);
  const [peekItem, setPeekItem] = useState<PoolProductItem | null>(null);
  const [peekOpen, setPeekOpen] = useState(false);

  const items = useMemo(
    () =>
      Object.values(favorites)
        .sort((a, b) => b.favoritedAt.localeCompare(a.favoritedAt))
        .map((snapshot) => snapshot.item),
    [favorites],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="surface-base overflow-hidden rounded-xl">
        {items.length === 0 ? (
          <EmptyState
            icon={Star}
            title="products.favorites.empty"
            description="products.favorites.emptyHint"
          />
        ) : (
          <Scrollable
            axis="both"
            className="max-h-[calc(100vh-16rem)] overflow-auto"
          >
            <Table className="min-w-[880px]">
              <ProductsTableHead />
              <TableBody>
                {items.map((item) => (
                  <ProductRow
                    key={item.id}
                    item={item}
                    onOpen={(opened) => {
                      setPeekItem(opened);
                      setPeekOpen(true);
                    }}
                  />
                ))}
              </TableBody>
            </Table>
          </Scrollable>
        )}
      </div>
      <ProductPeek item={peekItem} open={peekOpen} onOpenChange={setPeekOpen} />
    </div>
  );
}
