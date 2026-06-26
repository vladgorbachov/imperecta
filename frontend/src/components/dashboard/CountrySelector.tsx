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
}: CountrySelectorProps) {
  const { t } = useTranslation();

  if (loading) {
    return <Skeleton data-testid="country-selector-skeleton" className={cn("h-9 w-full max-w-[220px]", className)} />;
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
          "h-9 min-w-[10rem] gap-1.5 bg-[var(--glass-bg)] text-xs sm:min-w-[12rem] sm:text-sm",
          "border border-[var(--glass-border)] hover:border-[var(--glass-border-hover)]",
          className,
        )}
        aria-label={t("markets.countrySelector.placeholder")}
      >
        <Globe className="size-3.5 shrink-0 opacity-70" aria-hidden />
        <SelectValue>{displayValue}</SelectValue>
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
