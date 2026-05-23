/**
 * Products page with two tabs: All products (pool) and My products (user).
 * i18n keys: nav.products, products.*, common.*
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { PoolProductsTab } from "@/components/products/PoolProductsTab";
import { MyProductsTab } from "@/components/products/MyProductsTab";

export function ProductsPage() {
  const { i18n, t } = useTranslation();
  const [activeTab, setActiveTab] = useState<"pool" | "my">("pool");
  const locale = i18n.language;

  return (
    <div className="flex h-full flex-col pb-1">
      <PageHeader title="nav.products" />

      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as "pool" | "my")}
        className="mt-3 flex flex-1 flex-col"
      >
        <TabsList className="glass-card mb-3 w-fit rounded-lg p-1">
          <TabsTrigger value="pool" className="rounded-md px-3 text-xs">
            {t("products.tabs.all")}
          </TabsTrigger>
          <TabsTrigger value="my" className="rounded-md px-3 text-xs">
            {t("products.tabs.mine")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="pool" className="mt-0 flex-1">
          <PoolProductsTab locale={locale} />
        </TabsContent>

        <TabsContent value="my" className="mt-0 flex-1">
          <MyProductsTab locale={locale} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
