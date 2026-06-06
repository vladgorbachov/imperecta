import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useDisplayCurrency } from "@/hooks/useDisplayCurrency";
import { formatPrice } from "@/lib/formatters";
import type { ConvertiblePriceFields } from "@/lib/displayCurrency";
import { cn } from "@/lib/utils";

export interface PriceDisplayProps extends ConvertiblePriceFields {
  className?: string;
}

/**
 * Renders a price in the user's selected display currency.
 * Falls back to local currency with a "(no rate)" marker when conversion is missing.
 */
export function PriceDisplay({
  localAmount,
  localCurrency,
  displayAmount,
  displayCurrency: convertedCurrency,
  conversionAvailable,
  className,
}: PriceDisplayProps) {
  const { t } = useTranslation();
  const { displayCurrency, locale, resolveDisplayPrice } = useDisplayCurrency();
  const resolved = resolveDisplayPrice({
    localAmount,
    localCurrency,
    displayAmount,
    displayCurrency: convertedCurrency,
    conversionAvailable,
  });

  if (resolved.amount == null) {
    return <span className={className}>{t("common.dash")}</span>;
  }

  const formatted = formatPrice(
    resolved.amount,
    resolved.currency ?? displayCurrency,
    locale
  );

  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      <span>{formatted}</span>
      {resolved.noRate && (
        <TooltipProvider delayDuration={200}>
          <Tooltip>
            <TooltipTrigger asChild>
              <span
                className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground"
                aria-label={t("displayCurrency.noRate")}
              >
                <AlertTriangle className="size-3 shrink-0" aria-hidden />
                <span>{t("displayCurrency.noRate")}</span>
              </span>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs text-xs">
              {t("displayCurrency.noRateTooltip")}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </span>
  );
}
