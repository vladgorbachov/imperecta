/**
 * Ticker bar for Markets page: forex + crypto + commodities + fuel.
 * Uses GET /api/markets/ticker?country=... for data.
 * Marquee animation, pause on hover. Hidden when empty.
 */

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { keepPreviousData } from "@tanstack/react-query";
import { Globe } from "lucide-react";
import { marketsApi, marketsQueryKeys } from "@/api/markets";
import { safeFixed, safeNumber } from "@/lib/safeNumber";
import { resolveActiveCountry } from "@/lib/countryResolution";
import { CountrySelector } from "./CountrySelector";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const STALE_2H = 2 * 60 * 60 * 1000;

function formatTickerValue(
  item: { symbol: string; name: string | null; price: number; change_24h: number | null; currency: string | null }
): string {
  const sym = item.symbol ?? "";
  const isForex = sym.includes("/");
  const isFuel = /gasoline|diesel|lpg|petrol|fuel/i.test(sym);

  if (isForex) {
    const quote = sym.split("/")[1] ?? "";
    const decimals = ["USD", "GBP", "CHF", "JPY"].includes(quote) ? 4 : 2;
    return safeFixed(item.price, decimals);
  }
  if (isFuel) {
    const cur = item.currency ?? "UAH";
    return `${safeFixed(item.price, 1)} ${cur}/L`;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: item.currency ?? "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(safeNumber(item.price));
}

function TickerItem({
  item,
}: {
  item: { symbol: string; name: string | null; price: number; change_24h: number | null; currency: string | null };
}) {
  const ch = item.change_24h ?? 0;
  const isZero = ch === 0;
  const isPositive = ch > 0;
  const label = item.name ?? item.symbol ?? "";
  const value = formatTickerValue(item);

  return (
    <span className="inline-flex shrink-0 items-center gap-2">
      <span className="text-xs font-medium">{label}</span>
      <span className="font-mono text-sm">{value}</span>
      {item.change_24h != null && (
        <span
          className={cn(
            "text-xs font-mono",
            isZero ? "text-muted-foreground" : isPositive ? "text-[var(--color-price-down)]" : "text-[var(--color-price-up)]"
          )}
        >
          {isPositive ? "+" : ""}
          {safeFixed(ch, 1)}%
        </span>
      )}
    </span>
  );
}

export function MarketsTickerBar() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [manualSelection, setManualSelection] = useState<string | null>(null);

  const { data: prefs } = useQuery({
    queryKey: marketsQueryKeys.preferences(),
    queryFn: () => marketsApi.getPreferences().then((r) => r.data),
    staleTime: 60_000,
  });

  const saved = prefs?.preferred_country_code ?? null;
  const country = useMemo(
    () => resolveActiveCountry(saved, manualSelection, i18n.language),
    [saved, manualSelection, i18n.language]
  );

  const { data: tickerData, isLoading } = useQuery({
    queryKey: marketsQueryKeys.ticker(country),
    queryFn: () => marketsApi.getTicker(country).then((r) => r.data),
    staleTime: STALE_2H,
    refetchInterval: STALE_2H,
    placeholderData: keepPreviousData,
    enabled: !!country,
  });

  const items = tickerData?.items ?? [];
  const showTicker = items.length > 0;

  const updatePrefs = useMutation({
    mutationFn: (code: string) =>
      marketsApi.updatePreferences({ preferred_country_code: code }),
    onSuccess: (_, code) => {
      queryClient.invalidateQueries({ queryKey: marketsQueryKeys.preferences() });
      queryClient.invalidateQueries({ queryKey: marketsQueryKeys.ticker(code) });
      queryClient.invalidateQueries({ queryKey: marketsQueryKeys.fuel(code) });
      queryClient.invalidateQueries({ queryKey: marketsQueryKeys.forex() });
      toast.success(t("countries.saved"));
      setManualSelection(null);
    },
  });

  const handleSaveCountry = (code: string) => {
    updatePrefs.mutate(code);
  };

  if (isLoading && !prefs) {
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
            value={manualSelection ?? saved ?? country}
            onSelect={setManualSelection}
            onSave={handleSaveCountry}
            disabled={updatePrefs.isPending}
          />
        </div>
      </div>

      {showTicker && (
        <div className="group flex max-w-full overflow-hidden">
          <div className="flex animate-marquee gap-10 whitespace-nowrap group-hover:[animation-play-state:paused]">
            {[...items, ...items].map((item, i) => (
              <span key={`${item.symbol}-${i}`} className="flex shrink-0 items-center gap-2">
                <TickerItem item={item} />
                <span className="shrink-0 text-muted-foreground" style={{ width: 40 }}>
                  |
                </span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
