/**
 * Inline Settings panel: choose which forex / crypto / commodity instruments
 * appear in the global Header ticker.
 *
 * Persists via PUT /markets/preferences and invalidates both the preferences
 * and the ticker query so the marquee reflects the change.
 */

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  marketsApi,
  marketsQueryKeys,
  type MarketsInstrumentOption,
} from "@/api/markets";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

function sortByRankThenSymbol(
  options: MarketsInstrumentOption[],
): MarketsInstrumentOption[] {
  return [...options].sort((left, right) => {
    const leftRank = typeof left.rank === "number" ? left.rank : Number.MAX_SAFE_INTEGER;
    const rightRank = typeof right.rank === "number" ? right.rank : Number.MAX_SAFE_INTEGER;
    if (leftRank !== rightRank) return leftRank - rightRank;
    return left.symbol.localeCompare(right.symbol);
  });
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
        <p className="text-xs text-muted-foreground">
          {t("products.selectedCount", { count: selected.size })}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onSelectAll}>
          {t("products.selectAll")}
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onClear}>
          {t("products.clearSelection")}
        </Button>
      </div>
      <Input
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
        placeholder={t("common.search")}
      />
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
                    active
                      ? "border-primary bg-primary/10 text-foreground"
                      : "border-border text-foreground",
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

export function TickerSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

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

  const { data: instruments } = useQuery({
    queryKey: marketsQueryKeys.instruments(),
    queryFn: () => marketsApi.getInstruments().then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  });

  const forexOptions = instruments?.forex ?? [];
  const cryptoOptions = instruments?.crypto ?? [];
  const commodityOptions = instruments?.commodities ?? [];

  // Seed draft selections from server-side preferences whenever they (re)load.
  // Replaces the legacy `openConfig` handler used by the dialog flow.
  useEffect(() => {
    if (!prefs) return;
    setForexDraft(
      new Set((prefs.forex_favorites ?? []).map((value) => value.toUpperCase())),
    );
    setCryptoDraft(
      new Set((prefs.crypto_favorites ?? []).map((value) => value.toUpperCase())),
    );
    setCommodityDraft(
      new Set((prefs.commodity_favorites ?? []).map((value) => value.toUpperCase())),
    );
  }, [prefs]);

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

  const updateInstrumentPrefs = useMutation({
    mutationFn: (payload: {
      forex: string[];
      crypto: string[];
      commodities: string[];
    }) =>
      marketsApi.updatePreferences({
        forex_favorites: payload.forex,
        crypto_favorites: payload.crypto,
        commodity_favorites: payload.commodities,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketsQueryKeys.preferences() });
      queryClient.invalidateQueries({ queryKey: marketsQueryKeys.ticker() });
      toast.success(t("common.save"));
    },
  });

  const toggleSetValue = (
    setter: (next: Set<string>) => void,
    source: Set<string>,
    symbol: string,
  ) => {
    const next = new Set(source);
    if (next.has(symbol)) {
      next.delete(symbol);
    } else {
      next.add(symbol);
    }
    setter(next);
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2 rounded-lg border p-3">
        <p className="text-sm font-semibold">Quick presets</p>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setCryptoDraft(new Set(topVolumeCryptoPreset))}
          >
            Top volume
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setForexDraft(new Set(topFxMajorsPreset))}
          >
            Top FX majors
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setCommodityDraft(new Set(onlyMetalsPreset))}
          >
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
          onSelectAll={() =>
            setForexDraft(
              new Set(forexOptions.map((item) => item.symbol.toUpperCase())),
            )
          }
          onClear={() => setForexDraft(new Set())}
        />
        <InstrumentSection
          title={t("widgets.crypto.title")}
          options={cryptoOptions}
          selected={cryptoDraft}
          search={cryptoSearch}
          onSearchChange={setCryptoSearch}
          onToggle={(symbol) => toggleSetValue(setCryptoDraft, cryptoDraft, symbol)}
          onSelectAll={() =>
            setCryptoDraft(
              new Set(cryptoOptions.map((item) => item.symbol.toUpperCase())),
            )
          }
          onClear={() => setCryptoDraft(new Set())}
        />
        <InstrumentSection
          title={t("widgets.commodities.title")}
          options={commodityOptions}
          selected={commodityDraft}
          search={commoditySearch}
          onSearchChange={setCommoditySearch}
          onToggle={(symbol) =>
            toggleSetValue(setCommodityDraft, commodityDraft, symbol)
          }
          onSelectAll={() =>
            setCommodityDraft(
              new Set(commodityOptions.map((item) => item.symbol.toUpperCase())),
            )
          }
          onClear={() => setCommodityDraft(new Set())}
        />
      </div>

      <div>
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
      </div>
    </div>
  );
}
