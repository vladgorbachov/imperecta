/**
 * Four widgets above Market Overview: Forex, Crypto, Commodities, Fuel.
 * Each displays real API data with favorites (star) support.
 */

import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { keepPreviousData } from "@tanstack/react-query";
import { Star } from "lucide-react";
import {
  marketsApi,
  marketsQueryKeys,
} from "@/api/markets";
import { resolveActiveCountry } from "@/lib/countryResolution";
import { safeFixed, safeNumber } from "@/lib/safeNumber";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const STALE_2H = 2 * 60 * 60 * 1000;

function formatForexRate(rate: number | undefined, pair: string): string {
  const quote = pair.split("/")[1] ?? "";
  const decimals = ["USD", "GBP", "CHF", "JPY"].includes(quote) ? 4 : 2;
  return safeFixed(rate, decimals);
}

function formatCryptoPrice(price: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(safeNumber(price));
}

function useFavorites(): {
  favorites: Set<string>;
  toggleFavorite: (id: string) => void;
  isPending: boolean;
} {
  const queryClient = useQueryClient();
  const { data: prefs } = useQuery({
    queryKey: marketsQueryKeys.preferences(),
    queryFn: () => marketsApi.getPreferences().then((r) => r.data),
    staleTime: 60_000,
  });
  const favorites = useMemo(
    () => new Set<string>(prefs?.favorite_instrument_ids ?? []),
    [prefs?.favorite_instrument_ids]
  );
  const updatePrefs = useMutation({
    mutationFn: (ids: string[]) =>
      marketsApi.updatePreferences({ favorite_instrument_ids: ids }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketsQueryKeys.preferences() });
    },
  });
  const toggleFavorite = useCallback(
    (id: string) => {
      const next = new Set(favorites);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      updatePrefs.mutate([...next]);
    },
    [favorites, updatePrefs]
  );
  return { favorites, toggleFavorite, isPending: updatePrefs.isPending };
}

function ForexWidget() {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: marketsQueryKeys.forex(),
    queryFn: () => marketsApi.getForex().then((r) => r.data),
    staleTime: STALE_2H,
    refetchInterval: STALE_2H,
    placeholderData: keepPreviousData,
    retry: 1,
  });

  const { favorites, toggleFavorite, isPending } = useFavorites();

  const items = useMemo(() => {
    const raw = data?.items ?? [];
    const favSet = new Set(favorites);
    const favPairs = raw.filter((f) => favSet.has(f.symbol));
    const rest = raw.filter((f) => !favSet.has(f.symbol));
    const sortedFav = [...favPairs].sort((a, b) => a.symbol.localeCompare(b.symbol));
    const sortedRest = [...rest].sort((a, b) => a.symbol.localeCompare(b.symbol));
    return [...sortedFav, ...sortedRest];
  }, [data?.items, favorites]);

  if (isLoading && !data) {
    return <WidgetSkeleton title={t("widgets.forex.title")} />;
  }

  if (isError) {
    return (
      <WidgetCard title={t("widgets.forex.title")}>
        <p className="text-sm text-muted-foreground">{t("widgets.forex.unavailable")}</p>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-2 text-sm font-medium text-[var(--accent)] hover:underline"
        >
          {t("widgets.forex.retry")}
        </button>
      </WidgetCard>
    );
  }

  return (
    <WidgetCard title={t("widgets.forex.title")}>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("widgets.forex.unavailable")}</p>
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 8).map((f) => (
            <li key={f.symbol} className="flex items-center justify-between gap-2 text-sm">
              <span>{f.symbol}</span>
              <div className="flex items-center gap-4">
                <span className="font-mono">{formatForexRate(f.rate ?? f.bid, f.symbol)}</span>
                {f.change_24h != null && (
                  <span
                    className={cn(
                      "text-xs font-mono",
                      f.change_24h > 0 ? "text-[var(--color-price-down)]" : "text-[var(--color-price-up)]"
                    )}
                  >
                    {f.change_24h > 0 ? "+" : ""}
                    {safeFixed(f.change_24h, 1)}%
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => !isPending && toggleFavorite(f.symbol)}
                  disabled={isPending}
                  className="shrink-0 text-muted-foreground hover:text-amber-500 transition-colors"
                  title={favorites.has(f.symbol) ? t("widgets.favorite.remove") : t("widgets.favorite.add")}
                >
                  <Star
                    className={cn("size-4", favorites.has(f.symbol) ? "fill-amber-400 text-amber-400" : "fill-none")}
                  />
                </button>
              </div>
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
    staleTime: STALE_2H,
    refetchInterval: STALE_2H,
    placeholderData: keepPreviousData,
  });
  const { favorites, toggleFavorite, isPending } = useFavorites();

  const items = useMemo(() => {
    const raw = data?.items ?? [];
    const favSet = new Set(favorites);
    const fav = raw.filter((c) => favSet.has(c.symbol));
    const rest = raw.filter((c) => !favSet.has(c.symbol));
    return [...fav, ...rest];
  }, [data?.items, favorites]);

  if (isLoading && !data) {
    return <WidgetSkeleton title={t("widgets.crypto.title")} />;
  }

  return (
    <WidgetCard title={t("widgets.crypto.title")}>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("common.noData")}</p>
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 6).map((c) => (
            <li key={c.symbol} className="flex items-center justify-between gap-2 text-sm">
              <span className="font-semibold">{c.symbol}</span>
              <div className="flex items-center gap-4">
                <span className="font-mono">{formatCryptoPrice(c.price)}</span>
                {c.change_24h != null && (
                  <span
                    className={cn(
                      "text-xs font-mono",
                      c.change_24h > 0 ? "text-[var(--color-price-down)]" : c.change_24h < 0 ? "text-[var(--color-price-up)]" : "text-muted-foreground"
                    )}
                  >
                    {c.change_24h > 0 ? "+" : ""}
                    {safeFixed(c.change_24h, 1)}%
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => !isPending && toggleFavorite(c.symbol)}
                  disabled={isPending}
                  className="shrink-0 text-muted-foreground hover:text-amber-500 transition-colors"
                  title={favorites.has(c.symbol) ? t("widgets.favorite.remove") : t("widgets.favorite.add")}
                >
                  <Star
                    className={cn("size-4", favorites.has(c.symbol) ? "fill-amber-400 text-amber-400" : "fill-none")}
                  />
                </button>
              </div>
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
    staleTime: STALE_2H,
    refetchInterval: STALE_2H,
    placeholderData: keepPreviousData,
  });
  const { favorites, toggleFavorite, isPending } = useFavorites();

  const FUEL_SYMBOLS = new Set(["gasoline", "diesel", "gas", "lpg", "petrol"].map((s) => s.toLowerCase()));
  const items = useMemo(() => {
    const raw = (data?.items ?? []).filter((c) => !FUEL_SYMBOLS.has((c.symbol ?? "").toLowerCase()));
    const favSet = new Set(favorites);
    const fav = raw.filter((c) => favSet.has(c.symbol));
    const rest = raw.filter((c) => !favSet.has(c.symbol));
    return [...fav, ...rest];
  }, [data?.items, favorites]);

  if (isLoading && !data) {
    return <WidgetSkeleton title={t("widgets.commodities.title")} />;
  }

  if (items.length === 0) {
    return (
      <WidgetCard title={t("widgets.commodities.title")}>
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      </WidgetCard>
    );
  }

  return (
    <WidgetCard title={t("widgets.commodities.title")}>
      <ul className="space-y-2">
        {items.slice(0, 6).map((c) => (
          <li key={c.symbol} className="flex items-center justify-between gap-2 text-sm">
            <span>{c.name ?? c.symbol}</span>
            <div className="flex items-center gap-4">
              <span className="font-mono">
                ${safeFixed(c.price, 2)}/{c.unit ?? "oz"}
              </span>
              {c.change_24h != null && (
                <span
                  className={cn(
                    "text-xs font-mono",
                    c.change_24h > 0 ? "text-[var(--color-price-down)]" : "text-[var(--color-price-up)]"
                  )}
                >
                  {c.change_24h > 0 ? "+" : ""}
                  {safeFixed(c.change_24h, 1)}%
                </span>
              )}
              <button
                type="button"
                onClick={() => !isPending && toggleFavorite(c.symbol)}
                disabled={isPending}
                className="shrink-0 text-muted-foreground hover:text-amber-500 transition-colors"
                title={favorites.has(c.symbol) ? t("widgets.favorite.remove") : t("widgets.favorite.add")}
              >
                <Star
                  className={cn("size-4", favorites.has(c.symbol) ? "fill-amber-400 text-amber-400" : "fill-none")}
                />
              </button>
            </div>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}

function FuelWidget() {
  const { t } = useTranslation();
  const { data: prefs } = useQuery({
    queryKey: marketsQueryKeys.preferences(),
    queryFn: () => marketsApi.getPreferences().then((r) => r.data),
    staleTime: 60_000,
  });
  const selectedCountry = prefs?.preferred_country_code ?? "UA";
  const resolved = useMemo(
    () => resolveActiveCountry(selectedCountry, null, "en"),
    [selectedCountry]
  );

  const { data: fuelData } = useQuery({
    queryKey: marketsQueryKeys.fuel(resolved),
    queryFn: () => marketsApi.getFuel(resolved).then((r) => r.data),
    staleTime: STALE_2H,
    enabled: !!resolved && resolved !== "EUROPE" && resolved !== "CIS",
    retry: false,
  });

  const { data: fuelRegionData } = useQuery({
    queryKey: marketsQueryKeys.fuel(resolved),
    queryFn: () => marketsApi.getFuel(resolved).then((r) => r.data),
    staleTime: STALE_2H,
    enabled: resolved === "EUROPE" || resolved === "CIS",
    retry: false,
  });

  const fuel = fuelData ?? fuelRegionData;
  const isLoading = !prefs && !resolved;

  if (isLoading) {
    return <WidgetSkeleton title={t("widgets.fuel.title")} />;
  }

  if (!resolved) {
    return (
      <WidgetCard title={t("widgets.fuel.title")}>
        <p className="text-sm text-muted-foreground">{t("widgets.fuel.selectCountry")}</p>
      </WidgetCard>
    );
  }

  if (!fuel) {
    return (
      <WidgetCard title={t("widgets.fuel.title")}>
        <p className="text-sm text-muted-foreground">{t("widgets.fuel.unavailable")}</p>
      </WidgetCard>
    );
  }

  const { gasoline_95, diesel, lpg, currency, unit, updated } = fuel;
  const suffix = ` ${currency}/${unit}`;

  return (
    <WidgetCard title={t("widgets.fuel.title")}>
      <ul className="space-y-2">
        <li className="flex justify-between text-sm">
          <span>{t("widgets.fuel.gasoline")}</span>
          <span className="font-mono">
            {safeFixed(gasoline_95, 1)}
            {suffix}
          </span>
        </li>
        <li className="flex justify-between text-sm">
          <span>{t("widgets.fuel.diesel")}</span>
          <span className="font-mono">
            {safeFixed(diesel, 1)}
            {suffix}
          </span>
        </li>
        <li className="flex justify-between text-sm">
          <span>{t("widgets.fuel.lpg")}</span>
          <span className="font-mono">
            {safeFixed(lpg, 1)}
            {suffix}
          </span>
        </li>
      </ul>
      {updated && (
        <p className="mt-2 text-xs text-muted-foreground">
          {t("widgets.fuel.updated", { date: updated })}
        </p>
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
      className="rounded-xl p-4 transition-opacity duration-300"
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
