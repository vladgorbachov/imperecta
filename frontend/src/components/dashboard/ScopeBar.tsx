/**
 * Global scope bar for the Overview dashboard.
 * Holds the market context every widget below obeys: country + display currency.
 * Marketplace and period scopes join here in later slices (V-series).
 */

import { useTranslation } from "react-i18next";
import { CountrySelector } from "@/components/dashboard/CountrySelector";
import { DisplayCurrencySelector } from "@/components/ui/DisplayCurrencySelector";
import { useDashboardCountryStore } from "@/stores/dashboardCountryStore";

export function ScopeBar() {
  const { t } = useTranslation();
  const selectedCountry = useDashboardCountryStore((state) => state.selectedCountry);
  const setSelectedCountry = useDashboardCountryStore((state) => state.setSelectedCountry);
  const countryOptions = useDashboardCountryStore((state) => state.countryOptions);
  const optionsLoading = useDashboardCountryStore((state) => state.optionsLoading);

  return (
    <div className="surface-base flex flex-wrap items-center gap-2 rounded-lg px-3 py-2">
      <span className="label-mono me-1 hidden sm:inline">{t("dashboard.scope.label")}</span>
      <CountrySelector
        compact
        value={selectedCountry}
        onChange={setSelectedCountry}
        options={countryOptions}
        loading={optionsLoading}
      />
      <DisplayCurrencySelector compact />
    </div>
  );
}
