import { Coins } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DISPLAY_CURRENCY_OPTIONS,
  isDisplayCurrencyEnabled,
  type DisplayCurrency,
} from "@/lib/displayCurrency";
import { useDisplayCurrency } from "@/hooks/useDisplayCurrency";
import { cn } from "@/lib/utils";

interface DisplayCurrencySelectorProps {
  /** Compact: icon + code only */
  compact?: boolean;
  className?: string;
}

/**
 * Global display currency switcher for the app header.
 * EUR/USD are disabled until backend conversion is available.
 */
export function DisplayCurrencySelector({
  compact = true,
  className,
}: DisplayCurrencySelectorProps) {
  const { t } = useTranslation();
  const { displayCurrency, setDisplayCurrency } = useDisplayCurrency();

  const currentOption = DISPLAY_CURRENCY_OPTIONS.find(
    (option) => option.value === displayCurrency
  );
  const displayValue = compact
    ? displayCurrency === "local"
      ? t("displayCurrency.localShort")
      : displayCurrency
    : currentOption
      ? t(currentOption.labelKey)
      : displayCurrency;

  const handleChange = (value: string) => {
    const next = value as DisplayCurrency;
    if (isDisplayCurrencyEnabled(next)) {
      setDisplayCurrency(next);
    }
  };

  return (
    <Select value={displayCurrency} onValueChange={handleChange}>
      <SelectTrigger
        className={cn(
          compact ? "h-9 w-[5.5rem] gap-1 px-2" : "h-9 min-w-[10rem]",
          "bg-[var(--glass-bg)] border border-[var(--glass-border)]",
          "hover:border-[var(--glass-border-hover)] text-xs sm:text-sm",
          className
        )}
        aria-label={t("displayCurrency.label")}
      >
        {compact && <Coins className="size-3.5 shrink-0 opacity-70" aria-hidden />}
        <SelectValue>{displayValue}</SelectValue>
      </SelectTrigger>
      <SelectContent align="end">
        {DISPLAY_CURRENCY_OPTIONS.map((option) => {
          const enabled = isDisplayCurrencyEnabled(option.value);
          return (
            <SelectItem
              key={option.value}
              value={option.value}
              disabled={!enabled}
              className={cn(!enabled && "opacity-60")}
            >
              <span className="flex flex-col gap-0.5">
                <span className="flex items-center gap-2">
                  {t(option.labelKey)}
                  {!enabled && option.value !== "local" && (
                    <span className="text-[10px] text-muted-foreground">
                      ({t("displayCurrency.backendPending")})
                    </span>
                  )}
                </span>
                {!compact && (
                  <span className="text-[10px] text-muted-foreground">
                    {t(option.hintKey)}
                  </span>
                )}
              </span>
            </SelectItem>
          );
        })}
      </SelectContent>
    </Select>
  );
}
