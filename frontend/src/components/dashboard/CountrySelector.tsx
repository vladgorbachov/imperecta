import { Globe } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { getCountryByCode } from "@/lib/countries";
import { cn } from "@/lib/utils";

const ALL_COUNTRIES_VALUE = "__all__";

export interface CountrySelectorOption {
  code: string;
  label: string;
}

export interface CountrySelectorProps {
  value: string | null;
  onChange: (code: string | null) => void;
  options: CountrySelectorOption[];
  loading?: boolean;
  className?: string;
  /** Compact header treatment: icon on narrow viewports, truncated label on sm+. */
  compact?: boolean;
}

/**
 * Dashboard country scope selector. Options are supplied by the parent
 * (unscoped geo-coverage roll-up); this component never fetches.
 */
export function CountrySelector({
  value,
  onChange,
  options,
  loading = false,
  className,
  compact = false,
}: CountrySelectorProps) {
  const { t } = useTranslation();

  if (loading) {
    return (
      <Skeleton
        data-testid="country-selector-skeleton"
        className={cn(
          compact ? "h-9 w-9 sm:w-[7.5rem]" : "h-9 w-full max-w-[220px]",
          className,
        )}
      />
    );
  }

  const selectedValue = value ?? ALL_COUNTRIES_VALUE;

  const formatCountryLabel = (code: string, fallbackLabel: string): string => {
    const i18nKey = `countries.${code}`;
    const localized = t(i18nKey);
    if (localized !== i18nKey) {
      const flag = getCountryByCode(code)?.flag;
      return flag ? `${flag} ${localized}` : localized;
    }
    const flag = getCountryByCode(code)?.flag;
    return flag ? `${flag} ${fallbackLabel}` : fallbackLabel;
  };

  const displayValue =
    value == null
      ? t("markets.countrySelector.all")
      : formatCountryLabel(value, options.find((o) => o.code === value)?.label ?? value);

  return (
    <Select
      value={selectedValue}
      onValueChange={(next) => onChange(next === ALL_COUNTRIES_VALUE ? null : next)}
    >
      <SelectTrigger
        className={cn(
          compact
            ? [
                "h-9 min-h-9 w-9 min-w-9 max-w-9 justify-center px-0 touch-manipulation rounded-md text-xs",
                "sm:min-w-[7.5rem] sm:max-w-[9rem] sm:w-auto sm:justify-between sm:px-2.5 sm:text-xs",
              ]
            : "h-9 min-w-[10rem] gap-1.5 text-xs sm:min-w-[12rem] sm:text-sm",
          "bg-[var(--glass-bg)] border border-[var(--glass-border)] hover:border-[var(--glass-border-hover)]",
          "hover:shadow-[0_0_12px_var(--accent-glow)] transition-all duration-200",
          "ring-2 ring-[var(--accent)] shadow-[0_0_12px_var(--accent-glow)]",
          !compact && "gap-1.5",
          className,
        )}
        aria-label={t("markets.countrySelector.placeholder")}
      >
        <Globe
          className={cn("shrink-0 opacity-90", compact ? "size-4" : "size-3.5")}
          aria-hidden
        />
        <SelectValue className={cn(compact && "hidden sm:inline sm:truncate")}>
          {displayValue}
        </SelectValue>
      </SelectTrigger>
      <SelectContent align="start">
        <SelectItem value={ALL_COUNTRIES_VALUE}>{t("markets.countrySelector.all")}</SelectItem>
        {options.map((option) => (
          <SelectItem key={option.code} value={option.code}>
            {formatCountryLabel(option.code, option.label)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
