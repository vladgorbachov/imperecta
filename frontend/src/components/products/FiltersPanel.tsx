/**
 * Filters panel for ProductsPage: collapsible filter sections.
 * Supports checkbox, range, and select filter types.
 */

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { FilterConfig, FilterOption } from "@/types/filters";
import { formatPrice } from "@/lib/formatters";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const VISIBLE_OPTIONS_INITIAL = 5;

interface FiltersPanelProps {
  category?: string;
  filters: FilterConfig[];
  activeFilters: Record<string, string[]>;
  priceRange: {
    min: number;
    max: number;
    currentMin: number;
    currentMax: number;
  };
  onFilterChange: (filterId: string, values: string[]) => void;
  onPriceChange: (min: number, max: number) => void;
  onReset: () => void;
}

export function FiltersPanel({
  filters,
  activeFilters,
  priceRange,
  onFilterChange,
  onPriceChange,
  onReset,
}: FiltersPanelProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const hasAnyFilter =
    Object.values(activeFilters).some((arr) => arr.length > 0) ||
    priceRange.currentMin !== priceRange.min ||
    priceRange.currentMax !== priceRange.max;

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col overflow-hidden border-r border-border bg-background dark:border-border dark:bg-background">
      <div className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3 dark:border-border">
        <h2 className="text-sm font-semibold text-foreground dark:text-foreground">
          {t("filters.title")}
        </h2>
        {hasAnyFilter && (
          <Button variant="ghost" size="sm" className="h-8 text-xs" onClick={onReset}>
            {t("filters.reset")}
          </Button>
        )}
      </div>
      <div className="flex-1 overflow-y-auto">
        {filters.map((filter) => (
          <FilterSection
            key={filter.id}
            filter={filter}
            activeValues={activeFilters[filter.id] ?? []}
            priceRange={priceRange}
            locale={locale}
            onFilterChange={onFilterChange}
            onPriceChange={onPriceChange}
          />
        ))}
      </div>
    </aside>
  );
}

function FilterSection({
  filter,
  activeValues,
  priceRange,
  locale,
  onFilterChange,
  onPriceChange,
}: {
  filter: FilterConfig;
  activeValues: string[];
  priceRange: FiltersPanelProps["priceRange"];
  locale: string;
  onFilterChange: (id: string, values: string[]) => void;
  onPriceChange: (min: number, max: number) => void;
}) {
  const { t } = useTranslation();
  const hasActive = activeValues.length > 0 || filter.type === "range";
  const defaultOpen = hasActive;
  const [open, setOpen] = useState(defaultOpen);

  const appliedCount =
    filter.type === "range"
      ? priceRange.currentMin !== priceRange.min || priceRange.currentMax !== priceRange.max
        ? 1
        : 0
      : activeValues.length;

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="border-b border-border dark:border-border">
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm font-medium text-foreground transition-colors hover:bg-muted/50 dark:text-foreground dark:hover:bg-muted/50"
        >
          <span className="truncate">{t(filter.labelKey)}</span>
          <div className="flex shrink-0 items-center gap-1">
            {appliedCount > 0 && (
              <Badge variant="secondary" className="h-5 min-w-5 px-1.5 text-xs">
                {appliedCount}
              </Badge>
            )}
            {open ? (
              <ChevronUp className="size-4 text-muted-foreground dark:text-muted-foreground" />
            ) : (
              <ChevronDown className="size-4 text-muted-foreground dark:text-muted-foreground" />
            )}
          </div>
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="px-4 pb-4 pt-0">
          {filter.type === "checkbox" && filter.options && (
            <CheckboxFilter
              options={filter.options}
              activeValues={activeValues}
              onChange={(values) => onFilterChange(filter.id, values)}
            />
          )}
          {filter.type === "range" && (
            <RangeFilter
              priceRange={priceRange}
              locale={locale}
              onPriceChange={onPriceChange}
            />
          )}
          {filter.type === "select" && filter.options && (
            <SelectFilter
              options={filter.options}
              activeValues={activeValues}
              labelKey={filter.labelKey}
              onChange={(values) => onFilterChange(filter.id, values)}
            />
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function CheckboxFilter({
  options,
  activeValues,
  onChange,
}: {
  options: FilterOption[];
  activeValues: string[];
  onChange: (values: string[]) => void;
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const visibleCount = expanded ? options.length : VISIBLE_OPTIONS_INITIAL;
  const visibleOptions = options.slice(0, visibleCount);
  const remainingCount = options.length - visibleCount;

  const toggle = (value: string) => {
    const next = activeValues.includes(value)
      ? activeValues.filter((v) => v !== value)
      : [...activeValues, value];
    onChange(next);
  };

  return (
    <div className="space-y-2">
      {visibleOptions.map((opt) => (
        <label
          key={opt.value}
          className="flex cursor-pointer items-center gap-2 text-sm text-foreground dark:text-foreground"
        >
          <Checkbox
            checked={activeValues.includes(opt.value)}
            onCheckedChange={() => toggle(opt.value)}
          />
          <span className="flex-1 truncate">{opt.label}</span>
          {opt.count != null && (
            <span className="text-xs text-muted-foreground dark:text-muted-foreground">
              {opt.count}
            </span>
          )}
        </label>
      ))}
      {remainingCount > 0 && !expanded && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs"
          onClick={() => setExpanded(true)}
        >
          {t("filters.showMore", { count: remainingCount })}
        </Button>
      )}
      {expanded && options.length > VISIBLE_OPTIONS_INITIAL && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs"
          onClick={() => setExpanded(false)}
        >
          {t("filters.showLess")}
        </Button>
      )}
    </div>
  );
}

function RangeFilter({
  priceRange,
  locale,
  onPriceChange,
}: {
  priceRange: FiltersPanelProps["priceRange"];
  locale: string;
  onPriceChange: (min: number, max: number) => void;
}) {
  const { min, max, currentMin, currentMax } = priceRange;
  const [localMin, setLocalMin] = useState(String(currentMin));
  const [localMax, setLocalMax] = useState(String(currentMax));

  useEffect(() => {
    setLocalMin(String(currentMin));
    setLocalMax(String(currentMax));
  }, [currentMin, currentMax]);

  const applyMin = () => {
    const n = parseInt(localMin, 10);
    if (!Number.isNaN(n)) {
      const clamped = Math.max(min, Math.min(max, n));
      setLocalMin(String(clamped));
      onPriceChange(clamped, currentMax);
    }
  };

  const applyMax = () => {
    const n = parseInt(localMax, 10);
    if (!Number.isNaN(n)) {
      const clamped = Math.max(min, Math.min(max, n));
      setLocalMax(String(clamped));
      onPriceChange(currentMin, clamped);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input
          type="number"
          min={min}
          max={max}
          value={localMin}
          onChange={(e) => setLocalMin(e.target.value)}
          onBlur={applyMin}
          className="h-9 text-sm"
        />
        <Input
          type="number"
          min={min}
          max={max}
          value={localMax}
          onChange={(e) => setLocalMax(e.target.value)}
          onBlur={applyMax}
          className="h-9 text-sm"
        />
      </div>
      <p className="text-xs text-muted-foreground dark:text-muted-foreground">
        {formatPrice(currentMin, "RUB", locale)} – {formatPrice(currentMax, "RUB", locale)}
      </p>
    </div>
  );
}

function SelectFilter({
  options,
  activeValues,
  labelKey,
  onChange,
}: {
  options: FilterOption[];
  activeValues: string[];
  labelKey: string;
  onChange: (values: string[]) => void;
}) {
  const { t } = useTranslation();
  const value = activeValues[0] ?? "";

  return (
    <Select
      value={value}
      onValueChange={(v) => onChange(v ? [v] : [])}
    >
      <SelectTrigger className="h-9 w-full">
        <SelectValue placeholder={t(labelKey)} />
      </SelectTrigger>
      <SelectContent>
        {options.map((opt) => (
          <SelectItem key={opt.value} value={opt.value}>
            {opt.label}
            {opt.count != null && (
              <span className={cn("ml-2 text-muted-foreground dark:text-muted-foreground")}>
                {opt.count}
              </span>
            )}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
