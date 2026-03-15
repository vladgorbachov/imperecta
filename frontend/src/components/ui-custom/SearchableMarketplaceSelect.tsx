/**
 * Searchable marketplace dropdown for Add Competitor.
 * Fetches marketplaces from API. Alphabetical order.
 */

import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { MarketplaceBadge } from "@/components/ui-custom/MarketplaceBadge";
import { competitorsApi } from "@/api/competitors";

interface MarketplaceOption {
  marketplace_id: string;
  name: string;
}

interface SearchableMarketplaceSelectProps {
  value: string;
  onChange: (value: string) => void;
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
  const [marketplaces, setMarketplaces] = useState<MarketplaceOption[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function fetchMarketplaces() {
      setLoading(true);
      try {
        const res = await competitorsApi.listMarketplaces();
        setMarketplaces(res.data ?? []);
      } catch {
        setMarketplaces([]);
      } finally {
        setLoading(false);
      }
    }
    if (open) fetchMarketplaces();
  }, [open]);

  const filtered = marketplaces.filter((m) =>
    m.name.toLowerCase().includes(search.toLowerCase()) ||
    m.marketplace_id.toLowerCase().includes(search.toLowerCase())
  );

  const selected = marketplaces.find((m) => m.marketplace_id === value);

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
        <span className={selected ? "" : "text-muted-foreground"}>
          {selected ? (
            <span className="flex items-center gap-2">
              <MarketplaceBadge marketplace={selected.marketplace_id} size="sm" />
              {selected.name}
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
            {loading ? (
              <p className="px-2 py-4 text-center text-sm text-muted-foreground">
                {t("common.loading")}
              </p>
            ) : (
              filtered.map((m) => (
                <button
                  key={m.marketplace_id}
                  type="button"
                  className="flex w-full cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent hover:text-accent-foreground"
                  onClick={() => {
                    onChange(m.marketplace_id);
                    setOpen(false);
                    setSearch("");
                  }}
                >
                  <MarketplaceBadge marketplace={m.marketplace_id} size="sm" />
                  {m.name}
                </button>
              ))
            )}
            {!loading && filtered.length === 0 && (
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
