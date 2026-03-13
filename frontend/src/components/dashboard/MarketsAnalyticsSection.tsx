/**
 * Lower analytics section for Markets page.
 * Four blocks: Category/Segment Overview, Categories in Scope, Largest Marketplaces, Opportunities.
 * Uses real aggregates from stored snapshots. No hardcoded marketplace names.
 */

import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  marketsApi,
  marketsQueryKeys,
  type MarketsCategoryAnalyticsItem,
  type MarketsMarketplaceAnalyticsItem,
  type MarketsOpportunityBlockItem,
} from "@/api/markets";
import { Skeleton } from "@/components/ui/skeleton";
import { safeFixed } from "@/lib/safeNumber";
import { cn } from "@/lib/utils";

function formatChange(v: number): string {
  const sign = v >= 0 ? "+" : "";
  return `${sign}${safeFixed(v, 1)}%`;
}

export function MarketsAnalyticsSection() {
  const { t } = useTranslation();

  const { data: categoryData, isLoading: catLoading } = useQuery({
    queryKey: marketsQueryKeys.categoryAnalytics(),
    queryFn: async () => {
      const { data } = await marketsApi.getCategoryAnalytics();
      return data;
    },
  });

  const { data: marketplaceData, isLoading: mpLoading } = useQuery({
    queryKey: marketsQueryKeys.marketplaceAnalytics(),
    queryFn: async () => {
      const { data } = await marketsApi.getMarketplaceAnalytics();
      return data;
    },
  });

  const { data: opportunitiesData, isLoading: oppLoading } = useQuery({
    queryKey: marketsQueryKeys.opportunities(),
    queryFn: async () => {
      const { data } = await marketsApi.getOpportunities();
      return data;
    },
  });

  const categories = categoryData?.items ?? [];
  const marketplaces = marketplaceData?.items ?? [];
  const opportunities = opportunitiesData?.items ?? [];
  const isLoading = catLoading || mpLoading || oppLoading;

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-48 rounded-xl" />
        ))}
      </div>
    );
  }

  if (categories.length === 0 && marketplaces.length === 0 && opportunities.length === 0) {
    return (
      <div
        className="rounded-xl p-8 text-center text-sm"
        style={{ background: "var(--glass-bg)", color: "var(--foreground-muted)" }}
      >
        {t("markets.analytics.noData")}
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* 1. Category / Segment Overview */}
      <AnalyticsBlock title={t("markets.analytics.categoryOverview")}>
        {categories.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("markets.analytics.empty")}</p>
        ) : (
          <div className="space-y-2">
            {categories.slice(0, 5).map((c) => (
              <CategoryRow key={c.id} item={c} itemsLabel={t("markets.analytics.items")} />
            ))}
          </div>
        )}
      </AnalyticsBlock>

      {/* 2. Categories in This Scope */}
      <AnalyticsBlock title={t("markets.analytics.categoriesInScope")}>
        {categories.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("markets.analytics.empty")}</p>
        ) : (
          <ul className="space-y-1.5">
            {categories.map((c) => (
              <li
                key={c.id}
                className="flex items-center justify-between text-sm"
              >
                <span className="font-medium">{formatCategoryLabel(c.category_id)}</span>
                <span className="text-muted-foreground">
                  {(c.metrics?.item_count as number) ?? 0} {t("markets.analytics.items")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </AnalyticsBlock>

      {/* 3. Largest Marketplaces in This Scope */}
      <AnalyticsBlock title={t("markets.analytics.largestMarketplaces")}>
        {marketplaces.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("markets.analytics.empty")}</p>
        ) : (
          <ul className="space-y-1.5">
            {marketplaces
              .sort(
                (a, b) =>
                  ((b.metrics?.item_count as number) ?? 0) -
                  ((a.metrics?.item_count as number) ?? 0)
              )
              .slice(0, 10)
              .map((m) => (
                <MarketplaceRow key={m.id} item={m} />
              ))}
          </ul>
        )}
      </AnalyticsBlock>

      {/* 4. Marketplace Opportunities */}
      <AnalyticsBlock title={t("markets.analytics.marketplaceOpportunities")}>
        {opportunities.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("markets.analytics.empty")}</p>
        ) : (
          <div className="space-y-3">
            {opportunities.map((o) => (
              <OpportunityCard key={o.id} item={o} />
            ))}
          </div>
        )}
      </AnalyticsBlock>
    </div>
  );
}


function AnalyticsBlock({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-xl p-4"
      style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}
    >
      <h4 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h4>
      {children}
    </div>
  );
}

function formatCategoryLabel(categoryId: string): string {
  return categoryId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function CategoryRow({
  item,
  itemsLabel,
}: {
  item: MarketsCategoryAnalyticsItem;
  itemsLabel: string;
}) {
  const m = item.metrics as Record<string, unknown>;
  const avgChange = (m?.avg_change_24h as number) ?? 0;
  const itemCount = (m?.item_count as number) ?? 0;

  return (
    <div className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-[var(--glass-bg-hover)]">
      <span className="text-sm font-medium">{formatCategoryLabel(item.category_id)}</span>
      <div className="flex items-center gap-3 text-sm">
        <span className="text-muted-foreground">{itemCount} {itemsLabel}</span>
        <span
          className={cn(
            "font-mono",
            avgChange > 0 ? "text-[var(--color-price-down)]" : avgChange < 0 ? "text-[var(--color-price-up)]" : "text-muted-foreground"
          )}
        >
          {formatChange(avgChange)}
        </span>
      </div>
    </div>
  );
}

function MarketplaceRow({ item }: { item: MarketsMarketplaceAnalyticsItem }) {
  const m = item.metrics as Record<string, unknown>;
  const itemCount = (m?.item_count as number) ?? 0;
  const avgChange = (m?.avg_change_24h as number) ?? 0;
  const name = item.marketplace_name ?? item.marketplace_id;

  return (
    <li className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-[var(--glass-bg-hover)]">
      <span className="font-medium">{name}</span>
      <div className="flex items-center gap-3">
        <span className="text-muted-foreground">{itemCount}</span>
        <span
          className={cn(
            "font-mono text-xs",
            avgChange > 0 ? "text-[var(--color-price-down)]" : avgChange < 0 ? "text-[var(--color-price-up)]" : "text-muted-foreground"
          )}
        >
          {formatChange(avgChange)}
        </span>
      </div>
    </li>
  );
}

function OpportunityCard({ item }: { item: MarketsOpportunityBlockItem }) {
  const m = item.metrics as Record<string, unknown>;
  const count = (m?.count as number) ?? (m?.total_items as number) ?? 0;

  return (
    <div
      className="rounded-lg border px-3 py-2"
      style={{ borderColor: "var(--glass-border)" }}
    >
      <p className="text-sm font-medium">{item.title}</p>
      <p className="mt-1 text-xs text-muted-foreground">
        {count} {typeof m?.top_symbols === "object" && Array.isArray(m.top_symbols)
          ? `• ${(m.top_symbols as string[]).slice(0, 3).join(", ")}`
          : ""}
      </p>
    </div>
  );
}
