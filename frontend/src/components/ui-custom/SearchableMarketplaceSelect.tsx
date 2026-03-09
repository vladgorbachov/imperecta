/**
 * Searchable marketplace dropdown for Add Competitor.
 * Neutral ordering (alphabetical), no prioritization.
 * 5 visible items, scrollable, search by name.
 */

import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { MarketplaceBadge } from "@/components/ui-custom/MarketplaceBadge";
import { cn } from "@/lib/utils";

export type MarketplaceId = "kaspi" | "ozon" | "wildberries";

const MARKETPLACE_IDS: MarketplaceId[] = ["kaspi", "ozon", "wildberries"];

const I18N_KEYS: Record<MarketplaceId, string> = {
  kaspi: "competitors.marketplaceKaspi",
  ozon: "competitors.marketplaceOzon",
  wildberries: "competitors.marketplaceWb",
};

interface SearchableMarketplaceSelectProps {
  value: MarketplaceId | "";
  onChange: (value: MarketplaceId) => void;
  placeholder?: string;
}

export function SearchableMarketplaceSelect({
  value,
  onChange,
  placeholder,
}: SearchableMarketplaceSelectProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const sorted = [...MARKETPLACE_IDS].sort((a, b) =>
    t(I18N_KEYS[a]).localeCompare(t(I18N_KEYS[b]))
  );

  const filtered = sorted.filter((id) =>
    t(I18N_KEYS[id]).toLowerCase().includes(search.toLowerCase())
  );

  const selectedId = value || null;

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={ref} className="relative">
      <div
        className="flex h-10 w-full cursor-pointer items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2"
        onClick={() => setOpen(!open)}
      >
        <span className={selectedId ? "" : "text-muted-foreground"}>
          {selectedId ? (
            <span className="flex items-center gap-2">
              <MarketplaceBadge marketplace={selectedId} size="sm" />
              {t(I18N_KEYS[selectedId])}
            </span>
          ) : (
            placeholder ?? t("competitors.selectMarketplace")
          )}
        </span>
      </div>
      {open && (
        <div className="absolute top-full left-0 right-0 z-50 mt-1 overflow-hidden rounded-md border border-border bg-popover shadow-md dark:border-border dark:bg-popover">
          <Input
            placeholder={t("competitors.searchMarketplace")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="m-2 h-8"
            autoFocus
          />
          <div className="max-h-[160px] overflow-y-auto p-1">
            {filtered.map((id) => (
              <button
                key={id}
                type="button"
                className="flex w-full cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent hover:text-accent-foreground"
                onClick={() => {
                  onChange(id);
                  setOpen(false);
                  setSearch("");
                }}
              >
                <MarketplaceBadge marketplace={id} size="sm" />
                {t(I18N_KEYS[id])}
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="px-2 py-4 text-center text-sm text-muted-foreground">
                {t("competitors.noMatchingMarketplace")}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
