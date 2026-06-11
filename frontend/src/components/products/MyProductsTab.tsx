/**
 * "My Products" tab - placeholder.
 *
 * The user-products backend module is intentionally empty until Phase 4
 * (UP1). The full CRUD + import flow is rebuilt on top of the shared
 * Ingestion rail later. Until then this tab renders an honest empty state
 * so the surrounding ProductsPage continues to work for the pool tab.
 */

import { Package } from "lucide-react";

import { EmptyState } from "@/components/ui-custom/EmptyState";

interface MyProductsTabProps {
  locale: string;
}

export function MyProductsTab({ locale }: MyProductsTabProps) {
  void locale;
  return (
    <div className="flex h-full flex-col">
      <EmptyState
        icon={Package}
        title="products.tabs.mine"
        description="products.noProductsHint"
      />
    </div>
  );
}
