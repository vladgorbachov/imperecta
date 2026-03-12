/**
 * Searchable country dropdown for Markets page.
 * Saves selection to user preferences. First 10 visible, full scroll list.
 */

import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { COUNTRIES, type CountryInfo } from "@/lib/countries";
import { cn } from "@/lib/utils";

const INITIAL_VISIBLE = 10;

interface CountrySelectorProps {
  value: string | null;
  onSelect: (code: string) => void;
  onSave: (code: string) => void;
  disabled?: boolean;
}

export function CountrySelector({
  value,
  onSelect,
  onSave,
  disabled,
}: CountrySelectorProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [pendingCode, setPendingCode] = useState<string | null>(value);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) setPendingCode(value);
  }, [open, value]);

  const filtered = search.trim()
    ? COUNTRIES.filter((c) =>
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.code.toLowerCase().includes(search.toLowerCase())
      )
    : COUNTRIES;

  const displayList = filtered.slice(0, open ? undefined : INITIAL_VISIBLE);
  const hasMore = filtered.length > INITIAL_VISIBLE && !search.trim();

  const pendingCountry = pendingCode
    ? COUNTRIES.find((c) => c.code === pendingCode)
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
        <span className={cn(!pendingCountry && "text-muted-foreground")}>
          {pendingCountry
            ? pendingCountry.name
            : t("markets.countrySelector.placeholder")}
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
              placeholder={t("markets.countrySelector.search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9"
              autoFocus
            />
          </div>

          <div className="flex-1 overflow-y-auto p-1">
            {displayList.length === 0 ? (
              <p className="px-2 py-4 text-center text-sm text-muted-foreground">
                {t("markets.countrySelector.noResults")}
              </p>
            ) : (
              displayList.map((c) => (
                <CountryOption
                  key={c.code}
                  country={c}
                  selected={pendingCode === c.code}
                  onSelect={() => {
                    setPendingCode(c.code);
                    onSelect(c.code);
                  }}
                />
              ))
            )}
            {hasMore && (
              <p className="px-2 py-1 text-center text-xs text-muted-foreground">
                {t("markets.countrySelector.scrollForMore")}
              </p>
            )}
          </div>

          <div className="border-t p-2">
            <Button
              size="sm"
              className="w-full"
              onClick={handleSave}
              disabled={!pendingCode}
            >
              {t("markets.countrySelector.save")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function CountryOption({
  country,
  selected,
  onSelect,
}: {
  country: CountryInfo;
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
      <span>{country.name}</span>
      <span className="text-xs text-muted-foreground">{country.code}</span>
    </button>
  );
}
