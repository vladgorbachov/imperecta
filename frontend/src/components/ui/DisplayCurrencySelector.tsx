import { Coins } from "lucide-react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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
  /**
   * When true, the "Local" option is disabled and shows an explanatory tooltip.
   * Set by callers that scope the view to a single marketplace whose local
   * currency cannot be resolved (TLD generic + country_code uninformative).
   */
  localUnavailable?: boolean;
}

/**
 * Global display currency switcher for the app header.
 * EUR/USD are disabled until backend conversion is available.
 * "Local" is disabled when the caller scopes the view to a single marketplace
 * with no resolvable local currency.
 */
export function DisplayCurrencySelector({
  compact = true,
  className,
  localUnavailable = false,
}: DisplayCurrencySelectorProps) {
  const { t } = useTranslation();
  const { displayCurrency, setDisplayCurrency } = useDisplayCurrency();

  const context = { localUnavailable };

  useEffect(() => {
    if (localUnavailable && displayCurrency === "local") {
      const fallback: DisplayCurrency | undefined = (
        ["EUR", "USD"] as DisplayCurrency[]
      ).find((option) => isDisplayCurrencyEnabled(option, context));
      if (fallback) {
        setDisplayCurrency(fallback);
      }
    }
  }, [localUnavailable, displayCurrency, setDisplayCurrency]);

  const currentOption = DISPLAY_CURRENCY_OPTIONS.find(
    (option) => option.value === displayCurrency,
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
    if (isDisplayCurrencyEnabled(next, context)) {
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
          className,
        )}
        aria-label={t("displayCurrency.label")}
      >
        {compact && (
          <Coins className="size-3.5 shrink-0 opacity-70" aria-hidden />
        )}
        <SelectValue>{displayValue}</SelectValue>
      </SelectTrigger>
      <SelectContent align="end">
        <TooltipProvider delayDuration={150}>
          {DISPLAY_CURRENCY_OPTIONS.map((option) => {
            const enabled = isDisplayCurrencyEnabled(option.value, context);
            const localDisabled =
              option.value === "local" && localUnavailable;
            const item = (
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
                    {localDisabled && (
                      <span className="text-[10px] text-muted-foreground">
                        ({t("displayCurrency.localUnavailableShort")})
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
            if (!localDisabled) {
              return item;
            }
            return (
              <Tooltip key={option.value}>
                <TooltipTrigger asChild>
                  <div>{item}</div>
                </TooltipTrigger>
                <TooltipContent side="left" className="max-w-xs text-xs">
                  {t("displayCurrency.localUnavailableTooltip")}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </TooltipProvider>
      </SelectContent>
    </Select>
  );
}
