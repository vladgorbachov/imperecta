import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import {
  isDisplayCurrencyEnabled,
  resolvePriceForDisplay,
  type ConvertiblePriceFields,
  type DisplayCurrency,
  type ResolvedDisplayPrice,
} from "@/lib/displayCurrency";
import { formatPrice } from "@/lib/formatters";
import { useDisplayCurrencyStore } from "@/stores/displayCurrencyStore";

const PRICE_QUERY_PREFIXES = [
  ["markets"],
  ["pool-products"],
  ["products"],
  ["competitors"],
] as const;

/**
 * Global display currency preference with API param and formatting helpers.
 */
export function useDisplayCurrency() {
  const displayCurrency = useDisplayCurrencyStore((state) => state.displayCurrency);
  const setStoredCurrency = useDisplayCurrencyStore((state) => state.setDisplayCurrency);
  const queryClient = useQueryClient();
  const { i18n } = useTranslation();
  const locale = i18n.language || "en";

  const setDisplayCurrency = useCallback(
    (currency: DisplayCurrency) => {
      if (!isDisplayCurrencyEnabled(currency)) {
        return;
      }
      setStoredCurrency(currency);
      for (const queryKey of PRICE_QUERY_PREFIXES) {
        queryClient.invalidateQueries({ queryKey: [...queryKey] });
      }
    },
    [queryClient, setStoredCurrency]
  );

  const resolveDisplayPrice = useCallback(
    (fields: ConvertiblePriceFields): ResolvedDisplayPrice =>
      resolvePriceForDisplay(fields, displayCurrency),
    [displayCurrency]
  );

  const formatDisplayPrice = useCallback(
    (fields: ConvertiblePriceFields): string => {
      const resolved = resolvePriceForDisplay(fields, displayCurrency);
      if (resolved.amount == null || !resolved.currency) {
        return "—";
      }
      return formatPrice(resolved.amount, resolved.currency, locale);
    },
    [displayCurrency, locale]
  );

  return {
    displayCurrency,
    setDisplayCurrency,
    apiParam: displayCurrency,
    locale,
    resolveDisplayPrice,
    formatDisplayPrice,
  };
}
