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
import { marketsApi, marketsQueryKeys, type MarketsInstrumentOption } from "@/api/markets";
import { safeFixed, safeNumber } from "@/lib/safeNumber";
import { resolveActiveCountry } from "@/lib/countryResolution";
import { CountrySelector } from "./CountrySelector";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const STALE_2H = 2 * 60 * 60 * 1000;

function formatTickerValue(
  item: { symbol: string; name: string | null; price: number; change_24h: number | null; currency: string | null },
  locale: string
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
    const cur = item.currency ?? "";
    return `${safeFixed(item.price, 1)} ${cur}/L`;
  }
  const normalizedCurrency = (item.currency ?? "").trim().toUpperCase();
  if (!normalizedCurrency) {
    return safeFixed(item.price, 2);
  }
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: normalizedCurrency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(safeNumber(item.price));
  } catch {
    return `${safeFixed(item.price, 0)} ${normalizedCurrency}`;
  }
}

function TickerItem({
  item,
  locale,
}: {
  item: { symbol: string; name: string | null; price: number; change_24h: number | null; currency: string | null };
  locale: string;
}) {
  const ch = item.change_24h ?? 0;
  const isZero = ch === 0;
  const isPositive = ch > 0;
  const label = item.name ?? item.symbol ?? "";
  const value = formatTickerValue(item, locale);

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

function InstrumentSection({
  title,
  options,
  selected,
  search,
  onSearchChange,
  onToggle,
  onSelectAll,
  onClear,
}: {
  title: string;
  options: MarketsInstrumentOption[];
  selected: Set<string>;
  search: string;
  onSearchChange: (value: string) => void;
  onToggle: (symbol: string) => void;
  onSelectAll: () => void;
  onClear: () => void;
}) {
  const { t } = useTranslation();
  const visible = useMemo(() => {
    const query = search.trim().toUpperCase();
    if (!query) return options;
    return options.filter((item) => {
      const symbol = (item.symbol || "").toUpperCase();
      const name = (item.name || "").toUpperCase();
      return symbol.includes(query) || name.includes(query);
    });
  }, [options, search]);

  return (
    <div className="space-y-3 rounded-lg border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold">{title}</p>
        <p className="text-xs text-muted-foreground">{t("products.selectedCount", { count: selected.size })}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onSelectAll}>
          {t("products.selectAll")}
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onClear}>
          {t("products.clearSelection")}
        </Button>
      </div>
      <Input value={search} onChange={(event) => onSearchChange(event.target.value)} placeholder={t("common.search")} />
      <div className="max-h-48 overflow-auto rounded-md border p-2">
        {visible.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("common.noData")}</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {visible.map((item) => {
              const symbol = item.symbol.toUpperCase();
              const active = selected.has(symbol);
              return (
                <button
                  key={symbol}
                  type="button"
                  onClick={() => onToggle(symbol)}
                  className={cn(
                    "rounded-md border px-2 py-1 text-xs transition-colors",
                    active ? "border-primary bg-primary/10 text-primary" : "border-border text-foreground"
                  )}
                >
                  {item.name ? `${item.name} (${symbol})` : symbol}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function sortByRankThenSymbol(options: MarketsInstrumentOption[]): MarketsInstrumentOption[] {
  return [...options].sort((left, right) => {
    const leftRank = typeof left.rank === "number" ? left.rank : Number.MAX_SAFE_INTEGER;
    const rightRank = typeof right.rank === "number" ? right.rank : Number.MAX_SAFE_INTEGER;
    if (leftRank !== rightRank) return leftRank - rightRank;
    return left.symbol.localeCompare(right.symbol);
  });
}

export function MarketsTickerBar() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const queryClient = useQueryClient();
  const [manualSelection, setManualSelection] = useState<string | null>(null);
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [forexDraft, setForexDraft] = useState<Set<string>>(new Set());
  const [cryptoDraft, setCryptoDraft] = useState<Set<string>>(new Set());
  const [commodityDraft, setCommodityDraft] = useState<Set<string>>(new Set());
  const [forexSearch, setForexSearch] = useState("");
  const [cryptoSearch, setCryptoSearch] = useState("");
  const [commoditySearch, setCommoditySearch] = useState("");

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

  const { data: instruments } = useQuery({
    queryKey: marketsQueryKeys.instruments(),
    queryFn: () => marketsApi.getInstruments().then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  });

  const forexOptions = instruments?.forex ?? [];
  const cryptoOptions = instruments?.crypto ?? [];
  const commodityOptions = instruments?.commodities ?? [];

  const topVolumeCryptoPreset = useMemo(() => {
    return sortByRankThenSymbol(cryptoOptions)
      .slice(0, 10)
      .map((item) => item.symbol.toUpperCase());
  }, [cryptoOptions]);

  const topFxMajorsPreset = useMemo(() => {
    return sortByRankThenSymbol(forexOptions)
      .slice(0, 10)
      .map((item) => item.symbol.toUpperCase());
  }, [forexOptions]);

  const onlyMetalsPreset = useMemo(() => {
    return commodityOptions
      .filter((item) => (item.category || "").toLowerCase() === "metal")
      .map((item) => item.symbol.toUpperCase());
  }, [commodityOptions]);

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

  const updateInstrumentPrefs = useMutation({
    mutationFn: (payload: { forex: string[]; crypto: string[]; commodities: string[] }) =>
      marketsApi.updatePreferences({
        forex_favorites: payload.forex,
        crypto_favorites: payload.crypto,
        commodity_favorites: payload.commodities,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketsQueryKeys.preferences() });
      queryClient.invalidateQueries({ queryKey: marketsQueryKeys.ticker(country) });
      toast.success(t("common.save"));
      setIsConfigOpen(false);
    },
  });

  const openConfig = () => {
    setForexDraft(new Set((prefs?.forex_favorites ?? []).map((value) => value.toUpperCase())));
    setCryptoDraft(new Set((prefs?.crypto_favorites ?? []).map((value) => value.toUpperCase())));
    setCommodityDraft(new Set((prefs?.commodity_favorites ?? []).map((value) => value.toUpperCase())));
    setForexSearch("");
    setCryptoSearch("");
    setCommoditySearch("");
    setIsConfigOpen(true);
  };

  const toggleSetValue = (setter: (next: Set<string>) => void, source: Set<string>, symbol: string) => {
    const next = new Set(source);
    if (next.has(symbol)) {
      next.delete(symbol);
    } else {
      next.add(symbol);
    }
    setter(next);
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
        <Button type="button" variant="outline" size="sm" onClick={openConfig}>
          {t("common.edit")}
        </Button>
      </div>

      {showTicker && (
        <div className="group flex max-w-full overflow-hidden">
          <div className="flex animate-marquee gap-10 whitespace-nowrap group-hover:[animation-play-state:paused]">
            {[...items, ...items].map((item, i) => (
              <span key={`${item.symbol}-${i}`} className="flex shrink-0 items-center gap-2">
                <TickerItem item={item} locale={locale} />
                <span className="shrink-0 text-muted-foreground" style={{ width: 40 }}>
                  |
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      <Dialog open={isConfigOpen} onOpenChange={setIsConfigOpen}>
        <DialogContent className="max-h-[85vh] max-w-4xl overflow-auto">
          <DialogHeader>
            <DialogTitle>{t("filters.title")}</DialogTitle>
          </DialogHeader>

          <div className="space-y-2 rounded-lg border p-3">
            <p className="text-sm font-semibold">Quick presets</p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setCryptoDraft(new Set(topVolumeCryptoPreset))}>
                Top volume
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={() => setForexDraft(new Set(topFxMajorsPreset))}>
                Top FX majors
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={() => setCommodityDraft(new Set(onlyMetalsPreset))}>
                Only metals
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
            <InstrumentSection
              title={t("widgets.forex.title")}
              options={forexOptions}
              selected={forexDraft}
              search={forexSearch}
              onSearchChange={setForexSearch}
              onToggle={(symbol) => toggleSetValue(setForexDraft, forexDraft, symbol)}
              onSelectAll={() => setForexDraft(new Set(forexOptions.map((item) => item.symbol.toUpperCase())))}
              onClear={() => setForexDraft(new Set())}
            />
            <InstrumentSection
              title={t("widgets.crypto.title")}
              options={cryptoOptions}
              selected={cryptoDraft}
              search={cryptoSearch}
              onSearchChange={setCryptoSearch}
              onToggle={(symbol) => toggleSetValue(setCryptoDraft, cryptoDraft, symbol)}
              onSelectAll={() => setCryptoDraft(new Set(cryptoOptions.map((item) => item.symbol.toUpperCase())))}
              onClear={() => setCryptoDraft(new Set())}
            />
            <InstrumentSection
              title={t("widgets.commodities.title")}
              options={commodityOptions}
              selected={commodityDraft}
              search={commoditySearch}
              onSearchChange={setCommoditySearch}
              onToggle={(symbol) => toggleSetValue(setCommodityDraft, commodityDraft, symbol)}
              onSelectAll={() => setCommodityDraft(new Set(commodityOptions.map((item) => item.symbol.toUpperCase())))}
              onClear={() => setCommodityDraft(new Set())}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setIsConfigOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              type="button"
              disabled={updateInstrumentPrefs.isPending}
              onClick={() =>
                updateInstrumentPrefs.mutate({
                  forex: Array.from(forexDraft),
                  crypto: Array.from(cryptoDraft),
                  commodities: Array.from(commodityDraft),
                })
              }
            >
              {t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
