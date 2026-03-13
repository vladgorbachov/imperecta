/**
 * Searchable country dropdown for Markets page.
 * Fetches countries from API. Meta options (Europe, CIS) first, then separator, then countries.
 * Saves selection to markets preferences.
 */

import { useState, useRef, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Check, ChevronDown } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { marketsApi, marketsQueryKeys, type CountryItem } from "@/api/markets";
import { COUNTRY_NAMES_EN } from "@/lib/countryNames";
import { matchesCountrySearch } from "@/lib/countrySearch";
import { cn } from "@/lib/utils";

const INITIAL_VISIBLE = 10;
const LIST_MAX_HEIGHT = 300;

interface CountrySelectorProps {
  value: string | null;
  onSelect: (code: string) => void;
  onSave: (code: string) => void;
  disabled?: boolean;
}

function getDisplayName(item: CountryItem, t: (key: string) => string, locale: string): string {
  if (item.is_region) {
    return item.code === "EUROPE"
      ? t("countries.region.europe")
      : t("countries.region.cis");
  }
  const key = `countries.${item.code}`;
  return t(key, { defaultValue: item.name_local ?? item.name ?? COUNTRY_NAMES_EN[item.code] ?? item.name });
}

export function CountrySelector({
  value,
  onSelect,
  onSave,
  disabled,
}: CountrySelectorProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language ?? "en";
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [pendingCode, setPendingCode] = useState<string | null>(value);
  const ref = useRef<HTMLDivElement>(null);

  const { data: countriesData = [] } = useQuery({
    queryKey: marketsQueryKeys.countries(),
    queryFn: async () => {
      const { data } = await marketsApi.getCountries();
      return data;
    },
  });

  const metaOptions = useMemo(
    () => countriesData.filter((c) => c.is_region),
    [countriesData]
  );
  const separator = useMemo(
    () => countriesData.find((c) => c.separator),
    [countriesData]
  );
  const countryItems = useMemo(
    () => countriesData.filter((c) => !c.is_region && !c.separator),
    [countriesData]
  );

  const filteredCountries = useMemo(() => {
    const q = search.trim();
    if (!q) return countryItems;
    return countryItems.filter((c) =>
      matchesCountrySearch(
        c.name,
        c.code,
        q,
        locale
      ) || matchesCountrySearch(c.name_local ?? "", c.code, q, locale)
    );
  }, [search, countryItems, locale]);

  useEffect(() => {
    if (open) {
      setPendingCode(value);
      setSearch("");
    }
  }, [open, value]);

  const displayList = filteredCountries.slice(0, open ? undefined : INITIAL_VISIBLE);
  const hasMore = filteredCountries.length > INITIAL_VISIBLE && !search.trim();

  const pendingItem = pendingCode
    ? countriesData.find((c) => c.code === pendingCode)
    : null;
  const pendingDisplay = pendingItem
    ? getDisplayName(pendingItem, t, locale)
    : null;

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSave = () => {
    if (pendingCode) {
      onSave(pendingCode);
      onSelect(pendingCode);
      setOpen(false);
      setSearch("");
    }
  };

  const handleSelectMeta = (code: string) => {
    setPendingCode(code);
    onSelect(code);
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
        className={cn(
          "flex h-10 min-w-[180px] items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm",
          "border-input bg-background ring-offset-background",
          "focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-50",
          open && "ring-2 ring-ring ring-offset-2"
        )}
      >
        <span className={cn(!pendingDisplay && "text-muted-foreground")}>
          {pendingDisplay ?? t("markets.countrySelector.placeholder")}
        </span>
        <ChevronDown
          className={cn("size-4 shrink-0 opacity-50", open && "rotate-180")}
        />
      </button>

      {open && (
        <div
          className="absolute top-full left-0 z-50 mt-1 flex w-full min-w-[240px] flex-col overflow-hidden rounded-md border border-border bg-popover shadow-md"
          style={{ maxHeight: "min(400px, 70vh)" }}
        >
          <div className="border-b p-2">
            <Input
              placeholder={t("countries.search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9"
              autoFocus
            />
          </div>

          <div
            className="flex-1 overflow-y-auto p-1"
            style={{ maxHeight: LIST_MAX_HEIGHT }}
          >
            {metaOptions.length > 0 && (
              <div className="space-y-0.5 py-1">
                {metaOptions.map((item) => (
                  <button
                    key={item.code}
                    type="button"
                    onClick={() => handleSelectMeta(item.code)}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm transition-colors",
                      "hover:bg-accent hover:text-accent-foreground",
                      pendingCode === item.code && "bg-accent/80"
                    )}
                  >
                    <span>{item.flag}</span>
                    <span>{getDisplayName(item, t, locale)}</span>
                  </button>
                ))}
              </div>
            )}

            {separator && (
              <div className="my-1 border-t border-border" />
            )}

            {displayList.length === 0 && !search.trim() ? null : displayList.length === 0 ? (
              <p className="px-2 py-4 text-center text-sm text-muted-foreground">
                {t("markets.countrySelector.noResults")}
              </p>
            ) : (
              <div className="space-y-0.5">
                {displayList.map((c) => (
                  <CountryOption
                    key={c.code}
                    item={c}
                    displayName={getDisplayName(c, t, locale)}
                    selected={pendingCode === c.code}
                    onSelect={() => {
                      setPendingCode(c.code);
                      onSelect(c.code);
                    }}
                  />
                ))}
                {hasMore && (
                  <p className="px-2 py-1 text-center text-xs text-muted-foreground">
                    {t("markets.countrySelector.scrollForMore")}
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="border-t p-2">
            <Button
              size="sm"
              className="w-full"
              onClick={handleSave}
              disabled={!pendingCode}
            >
              {t("countries.save")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function CountryOption({
  item,
  displayName,
  selected,
  onSelect,
}: {
  item: CountryItem;
  displayName: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-left text-sm transition-colors",
        "hover:bg-accent hover:text-accent-foreground",
        selected && "bg-accent/80"
      )}
    >
      <span className="flex items-center gap-2">
        {item.flag && <span>{item.flag}</span>}
        <span>{displayName}</span>
      </span>
      {selected ? (
        <Check className="size-4 text-[var(--accent)]" />
      ) : (
        <span className="text-xs text-muted-foreground">{item.code}</span>
      )}
    </button>
  );
}
