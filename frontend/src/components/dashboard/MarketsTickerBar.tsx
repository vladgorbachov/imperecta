/**
 * Ticker bar for Markets page: fuel prices + FX pairs for active country.
 * Country selector integrated. Degraded state when fuel data unavailable.
 */

import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Globe } from "lucide-react";
import {
  marketsApi,
  marketsQueryKeys,
} from "@/api/markets";
import { resolveActiveCountry } from "@/lib/countryResolution";
import { buildTickerBarItems, type TickerBarItem } from "@/lib/tickerBarData";
import { CountrySelector } from "./CountrySelector";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function formatPrice(price: number, currency: string | null): string {
  const cur = currency ?? "USD";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: cur,
    minimumFractionDigits: 2,
    maximumFractionDigits: 0,
  }).format(price);
}

function TickerItem({ item }: { item: TickerBarItem }) {
  const ch = item.change_24h ?? 0;
  const isZero = ch === 0;
  const isPositive = ch > 0;

  return (
    <div
      className="flex shrink-0 items-center gap-2 rounded-md px-3 py-1.5"
      style={{ background: "var(--glass-bg)" }}
    >
      <span className="text-xs font-medium">{item.name}</span>
      <span className="font-mono text-sm">{formatPrice(item.price, item.currency)}</span>
      {item.change_24h != null && (
        <span
          className={cn(
            "text-xs font-mono",
            isZero ? "text-muted-foreground" : isPositive ? "text-[var(--color-price-down)]" : "text-[var(--color-price-up)]"
          )}
        >
          {isPositive ? "+" : ""}
          {ch.toFixed(1)}%
        </span>
      )}
    </div>
  );
}

export function MarketsTickerBar() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [manualSelection, setManualSelection] = useState<string | null>(null);

  const { data: prefs } = useQuery({
    queryKey: marketsQueryKeys.preferences(),
    queryFn: async () => {
      const { data } = await marketsApi.getPreferences();
      return data;
    },
  });

  const { data: forexData } = useQuery({
    queryKey: marketsQueryKeys.forex(),
    queryFn: async () => {
      const { data } = await marketsApi.getForex();
      return data;
    },
  });

  const { data: commoditiesData } = useQuery({
    queryKey: marketsQueryKeys.commodities(),
    queryFn: async () => {
      const { data } = await marketsApi.getCommodities();
      return data;
    },
  });

  const updatePrefs = useMutation({
    mutationFn: (countryCode: string) =>
      marketsApi.updatePreferences({ preferred_country_code: countryCode }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketsQueryKeys.preferences() });
    },
  });

  const { countryCode, items, fuelAvailable, isLoading } = useMemo(() => {
    const saved = prefs?.preferred_country_code ?? null;
    const country = resolveActiveCountry(saved, manualSelection, i18n.language);
    const forex = forexData?.items ?? [];
    const commodities = commoditiesData?.items ?? [];
    const tickerItems = buildTickerBarItems(forex, commodities, country);
    const fuelItems = tickerItems.filter((i) => i.type === "fuel");
    const fuelAvailable = fuelItems.length > 0;

    return {
      countryCode: country,
      items: tickerItems,
      fuelAvailable,
      isLoading: !prefs && !forexData && !commoditiesData,
    };
  }, [prefs, forexData, commoditiesData, i18n.language, manualSelection]);

  const handleSaveCountry = (code: string) => {
    updatePrefs.mutate(code);
    setManualSelection(null);
  };

  const handleSelectCountry = (code: string) => {
    setManualSelection(code);
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-4 rounded-xl p-4" style={{ background: "var(--glass-bg)" }}>
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-8 w-full max-w-md" />
      </div>
    );
  }

  return (
    <div
      className="flex flex-col gap-3 rounded-xl p-4 sm:flex-row sm:items-center sm:justify-between"
      style={{ background: "var(--glass-bg)" }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2">
          <Globe className="size-4 text-muted-foreground" />
          <CountrySelector
            value={manualSelection ?? prefs?.preferred_country_code ?? countryCode}
            onSelect={handleSelectCountry}
            onSave={handleSaveCountry}
            disabled={updatePrefs.isPending}
          />
        </div>

        {!fuelAvailable && items.length > 0 && (
          <span className="text-xs text-muted-foreground">
            {t("markets.ticker.fuelUnavailable")}
          </span>
        )}

        {items.length === 0 && (
          <span className="text-sm text-muted-foreground">
            {t("markets.ticker.noData")}
          </span>
        )}
      </div>

      <div className="flex overflow-x-auto gap-2 pb-1 scrollbar-thin">
        {items.map((item) => (
          <TickerItem key={`${item.type}-${item.symbol}`} item={item} />
        ))}
      </div>
    </div>
  );
}
