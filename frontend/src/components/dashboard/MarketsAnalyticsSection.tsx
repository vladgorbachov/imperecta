import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { marketsApi, marketsQueryKeys } from "@/api/markets";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { ErrorState } from "@/components/ui-custom/ErrorState";
import { useMarketplaceLabelFormatter } from "@/hooks/useMarketplaceLabel";
import { Skeleton } from "@/components/ui/skeleton";

export function MarketsAnalyticsSection() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const formatMarketplaceLabel = useMarketplaceLabelFormatter();

  const {
    data: marketplaceStats,
    isLoading: statsLoading,
    isError: statsError,
    refetch: refetchStats,
  } = useQuery({
    queryKey: marketsQueryKeys.poolMarketplaceStats(),
    queryFn: async () => {
      const { data } = await marketsApi.getPoolMarketplaceStats();
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });

  const {
    data: poolStats,
    isLoading: poolLoading,
    isError: poolError,
    refetch: refetchPool,
  } = useQuery({
    queryKey: marketsQueryKeys.poolStats(),
    queryFn: async () => {
      const { data } = await marketsApi.getPoolStats();
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });

  const rows = marketplaceStats ?? [];
  const isLoading = statsLoading || poolLoading;
  const isError = statsError || poolError;

  if (isError) {
    return (
      <ErrorState
        title="common.error"
        retry={{
          label: "common.refresh",
          onClick: () => {
            void refetchStats();
            void refetchPool();
          },
        }}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-48 rounded-xl" />
        ))}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <EmptyState
        bordered
        icon={AlertTriangle}
        title="markets.analytics.noMarketplaceData"
        description=""
      />
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <AnalyticsBlock title={t("markets.analytics.categoryOverview")}>
        <div className="space-y-2">
          {rows.slice(0, 8).map((item) => (
            <div
              key={item.marketplace_domain}
              className="flex items-center justify-between rounded-md px-2 py-1.5 transition-colors hover:bg-[var(--glass-bg-hover)]"
            >
              <span className="truncate text-sm font-medium">
                {formatMarketplaceLabel({
                  name: item.marketplace_name,
                  domain: item.marketplace_domain,
                  countryCode: item.country_code,
                }) || item.marketplace_domain}
              </span>
              <span className="text-sm text-muted-foreground">{item.product_count}</span>
            </div>
          ))}
        </div>
      </AnalyticsBlock>

      <AnalyticsBlock title={t("markets.analytics.categoriesInScope")}>
        <ul className="space-y-1.5">
          {rows.map((item) => (
            <li key={item.marketplace_domain} className="flex items-center justify-between text-sm">
              <span className="truncate font-medium">
                {formatMarketplaceLabel({
                  name: item.marketplace_name,
                  domain: item.marketplace_domain,
                  countryCode: item.country_code,
                }) || item.marketplace_domain}
              </span>
              <span className="text-muted-foreground">
                {t("markets.analytics.itemsCount", { count: item.product_count })}
              </span>
            </li>
          ))}
        </ul>
      </AnalyticsBlock>

      <AnalyticsBlock title={t("markets.analytics.poolStats")}>
        {poolStats ? (
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">{t("markets.analytics.totalProducts")}</span>
              <span className="font-medium">{poolStats.total_products}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">{t("markets.analytics.marketplaces")}</span>
              <span className="font-medium">{poolStats.marketplaces_count}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">{t("markets.analytics.withPrice")}</span>
              <span className="font-medium">{poolStats.listings_with_price}</span>
            </div>
            <div className="rounded-md border border-border bg-background/60 px-2 py-1 text-xs text-muted-foreground">
              {t("markets.analytics.lastUpdate")}:{" "}
              {poolStats.last_updated
                ? new Date(poolStats.last_updated).toLocaleString(locale)
                : t("common.dash")}
            </div>
          </div>
        ) : (
          <EmptyState title="markets.analytics.noStatsData" description="" />
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
    <div className="surface-base rounded-xl p-4">
      <h4 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h4>
      {children}
    </div>
  );
}
