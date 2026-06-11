import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { marketsApi, marketsQueryKeys } from "@/api/markets";
import { useMarketplaceLabelFormatter } from "@/hooks/useMarketplaceLabel";
import { Skeleton } from "@/components/ui/skeleton";

export function MarketsAnalyticsSection() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const formatMarketplaceLabel = useMarketplaceLabelFormatter();

  const { data: marketplaceStats, isLoading: statsLoading } = useQuery({
    queryKey: marketsQueryKeys.poolMarketplaceStats(),
    queryFn: async () => {
      const { data } = await marketsApi.getPoolMarketplaceStats();
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });

  const { data: poolStats, isLoading: poolLoading } = useQuery({
    queryKey: marketsQueryKeys.poolStats(),
    queryFn: async () => {
      const { data } = await marketsApi.getPoolStats();
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });

  const rows = marketplaceStats ?? [];
  const isLoading = statsLoading || poolLoading;

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
      <div
        className="rounded-xl p-8 text-center text-sm"
        style={{ background: "var(--glass-bg)", color: "var(--foreground-muted)" }}
      >
        {t("markets.analytics.noMarketplaceData")}
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <AnalyticsBlock title={t("markets.analytics.categoryOverview")}>
        <div className="space-y-2">
          {rows.slice(0, 8).map((item) => (
            <div
              key={item.marketplace_domain}
              className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-[var(--glass-bg-hover)]"
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
          <p className="text-sm text-muted-foreground">{t("markets.analytics.noStatsData")}</p>
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
