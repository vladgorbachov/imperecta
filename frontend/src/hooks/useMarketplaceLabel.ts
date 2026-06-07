import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  formatMarketplaceLabel,
  type MarketplaceLabelInput,
} from "@/lib/marketplaceLabel";

/** Returns a stable formatter for marketplace display labels in the current locale. */
export function useMarketplaceLabelFormatter() {
  const { i18n } = useTranslation();
  const locale = i18n.language || "en";

  return useMemo(
    () => (input: MarketplaceLabelInput) =>
      formatMarketplaceLabel({ ...input, locale }),
    [locale],
  );
}
