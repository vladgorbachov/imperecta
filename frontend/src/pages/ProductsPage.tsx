/**
 * Products page with two tabs: All products (pool) and My products (user).
 * i18n keys: nav.products, products.*, common.*
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Star } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { PoolProductsTab } from "@/components/products/PoolProductsTab";
import { FavoritesTab } from "@/components/products/FavoritesTab";
import { MyProductsTab } from "@/components/products/MyProductsTab";
import { useFavoritesStore } from "@/stores/favoritesStore";

export function ProductsPage() {
  const { i18n, t } = useTranslation();
  const [activeTab, setActiveTab] = useState<"pool" | "favorites" | "my">("pool");
  const locale = i18n.language;
  const favoritesCount = useFavoritesStore((state) => Object.keys(state.favorites).length);

  return (
    <div className="flex h-full flex-col pb-1">
      <PageHeader title="nav.products" />

      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as "pool" | "favorites" | "my")}
        className="mt-3 flex flex-1 flex-col"
      >
        <TabsList className="surface-base mb-3 w-fit rounded-lg p-1">
          <TabsTrigger value="pool" className="rounded-md px-3 text-xs">
            {t("products.tabs.all")}
          </TabsTrigger>
          <TabsTrigger value="favorites" className="rounded-md px-3 text-xs">
            <Star className="me-1 size-3" />
            {t("products.tabs.favorites")}
            {favoritesCount > 0 ? (
              <span className="ms-1.5 tabular-nums text-muted-foreground">
                {favoritesCount}
              </span>
            ) : null}
          </TabsTrigger>
          <TabsTrigger value="my" className="rounded-md px-3 text-xs">
            {t("products.tabs.mine")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="pool" className="mt-0 flex-1">
          <PoolProductsTab />
        </TabsContent>

        <TabsContent value="favorites" className="mt-0 flex-1">
          <FavoritesTab />
        </TabsContent>

        <TabsContent value="my" className="mt-0 flex-1">
          <MyProductsTab locale={locale} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
