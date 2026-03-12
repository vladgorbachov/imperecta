/**
 * Four widgets above Market Overview: Forex, Crypto, Commodities, Fuel.
 * Each displays its data type. Fuel is filtered from commodities.
 */

import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  marketsApi,
  marketsQueryKeys,
  type MarketsForexItem,
  type MarketsCryptoItem,
  type MarketsCommodityItem,
} from "@/api/markets";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const FUEL_SYMBOLS = new Set(
  ["gasoline", "diesel", "gas", "lpg", "petrol"].map((s) => s.toLowerCase())
);

function isFuel(symbol: string): boolean {
  return FUEL_SYMBOLS.has(symbol.toLowerCase());
}

function formatPrice(price: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(price);
}

function ForexWidget() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: marketsQueryKeys.forex(),
    queryFn: () => marketsApi.getForex().then((r) => r.data),
  });
  const items: MarketsForexItem[] = data?.items ?? [];

  if (isLoading) {
    return <WidgetSkeleton title={t("markets.widgets.forex")} />;
  }

  return (
    <WidgetCard title={t("markets.widgets.forex")}>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("markets.widgets.noData")}</p>
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 6).map((f) => (
            <li key={f.symbol} className="flex justify-between text-sm">
              <span>{f.symbol}</span>
              <span className="font-mono">
                {formatPrice(f.bid, "USD")}
                {f.change_24h != null && (
                  <span
                    className={cn(
                      "ml-1 text-xs",
                      f.change_24h > 0 ? "text-[var(--color-price-down)]" : "text-[var(--color-price-up)]"
                    )}
                  >
                    {f.change_24h > 0 ? "+" : ""}
                    {f.change_24h.toFixed(1)}%
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </WidgetCard>
  );
}

function CryptoWidget() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: marketsQueryKeys.crypto(),
    queryFn: () => marketsApi.getCrypto().then((r) => r.data),
  });
  const items: MarketsCryptoItem[] = data?.items ?? [];

  if (isLoading) {
    return <WidgetSkeleton title={t("markets.widgets.crypto")} />;
  }

  return (
    <WidgetCard title={t("markets.widgets.crypto")}>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("markets.widgets.noData")}</p>
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 6).map((c) => (
            <li key={c.symbol} className="flex justify-between text-sm">
              <span>{c.symbol}</span>
              <span className="font-mono">
                {formatPrice(c.price, "USD")}
                {c.change_24h != null && (
                  <span
                    className={cn(
                      "ml-1 text-xs",
                      c.change_24h > 0 ? "text-[var(--color-price-down)]" : "text-[var(--color-price-up)]"
                    )}
                  >
                    {c.change_24h > 0 ? "+" : ""}
                    {c.change_24h.toFixed(1)}%
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </WidgetCard>
  );
}

function CommoditiesWidget() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: marketsQueryKeys.commodities(),
    queryFn: () => marketsApi.getCommodities().then((r) => r.data),
  });
  const all: MarketsCommodityItem[] = data?.items ?? [];
  const items = all.filter((c) => !isFuel(c.symbol));

  if (isLoading) {
    return <WidgetSkeleton title={t("markets.widgets.commodities")} />;
  }

  return (
    <WidgetCard title={t("markets.widgets.commodities")}>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("markets.widgets.noData")}</p>
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 6).map((c) => (
            <li key={c.symbol} className="flex justify-between text-sm">
              <span>{c.name ?? c.symbol}</span>
              <span className="font-mono">
                {formatPrice(c.price, c.unit ?? "USD")}
                {c.change_24h != null && (
                  <span
                    className={cn(
                      "ml-1 text-xs",
                      c.change_24h > 0 ? "text-[var(--color-price-down)]" : "text-[var(--color-price-up)]"
                    )}
                  >
                    {c.change_24h > 0 ? "+" : ""}
                    {c.change_24h.toFixed(1)}%
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </WidgetCard>
  );
}

function FuelWidget() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: marketsQueryKeys.commodities(),
    queryFn: () => marketsApi.getCommodities().then((r) => r.data),
  });
  const all: MarketsCommodityItem[] = data?.items ?? [];
  const items = all.filter((c) => isFuel(c.symbol));

  if (isLoading) {
    return <WidgetSkeleton title={t("markets.widgets.fuel")} />;
  }

  return (
    <WidgetCard title={t("markets.widgets.fuel")}>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("markets.widgets.fuelUnavailable")}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((c) => (
            <li key={c.symbol} className="flex justify-between text-sm">
              <span>{c.name ?? c.symbol}</span>
              <span className="font-mono">
                {formatPrice(c.price, c.unit ?? "USD")}
                {c.change_24h != null && (
                  <span
                    className={cn(
                      "ml-1 text-xs",
                      c.change_24h > 0 ? "text-[var(--color-price-down)]" : "text-[var(--color-price-up)]"
                    )}
                  >
                    {c.change_24h > 0 ? "+" : ""}
                    {c.change_24h.toFixed(1)}%
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </WidgetCard>
  );
}

function WidgetCard({
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

function WidgetSkeleton({ title }: { title: string }) {
  return (
    <div
      className="rounded-xl p-4"
      style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}
    >
      <h4 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h4>
      <div className="space-y-2">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-4 w-full" />
        ))}
      </div>
    </div>
  );
}

export function MarketsWidgetsSection() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <ForexWidget />
      <CryptoWidget />
      <CommoditiesWidget />
      <FuelWidget />
    </div>
  );
}
