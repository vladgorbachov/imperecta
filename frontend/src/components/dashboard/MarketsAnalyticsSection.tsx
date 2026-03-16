import { useQuery } from "@tanstack/react-query";
import { marketsApi, marketsQueryKeys } from "@/api/markets";
import { Skeleton } from "@/components/ui/skeleton";

export function MarketsAnalyticsSection() {
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
        Нет данных по маркетплейсам. Discovery crawler ещё наполняет пул.
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <AnalyticsBlock title="Обзор категорий/сегментов">
        <div className="space-y-2">
          {rows.slice(0, 8).map((item) => (
            <div
              key={item.marketplace_domain}
              className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-[var(--glass-bg-hover)]"
            >
              <span className="truncate text-sm font-medium">
                {item.marketplace_name || item.marketplace_domain}
              </span>
              <span className="text-sm text-muted-foreground">{item.product_count}</span>
            </div>
          ))}
        </div>
      </AnalyticsBlock>

      <AnalyticsBlock title="Категории в охвате">
        <ul className="space-y-1.5">
          {rows.map((item) => (
            <li key={item.marketplace_domain} className="flex items-center justify-between text-sm">
              <span className="truncate font-medium">
                {item.marketplace_name || item.marketplace_domain}
              </span>
              <span className="text-muted-foreground">{item.product_count} товаров</span>
            </li>
          ))}
        </ul>
      </AnalyticsBlock>

      <AnalyticsBlock title="Статистика пула">
        {poolStats ? (
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Всего товаров</span>
              <span className="font-medium">{poolStats.total_products}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Маркетплейсов</span>
              <span className="font-medium">{poolStats.total_marketplaces}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">С ценой</span>
              <span className="font-medium">{poolStats.products_with_price}</span>
            </div>
            <div className="pt-1 text-xs text-muted-foreground">
              Последнее обновление:{" "}
              {poolStats.last_discovery_at
                ? new Date(poolStats.last_discovery_at).toLocaleString("ru-RU")
                : "—"}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Нет данных по статистике.</p>
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
