/**
 * Global scope bar for the Overview dashboard.
 * Holds the market context every widget below obeys: country + display currency.
 * Mounts into the layout header via the #header-page-slot portal so scope and
 * chrome share a single header row; falls back to inline rendering when the
 * slot is absent (tests, standalone rendering).
 */

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
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

  const [slot, setSlot] = useState<HTMLElement | null>(null);
  useEffect(() => {
    setSlot(document.getElementById("header-page-slot"));
  }, []);

  const controls = (
    <div
      className={
        slot
          ? "flex min-w-0 flex-wrap items-center gap-2"
          : "surface-base flex flex-wrap items-center gap-2 rounded-lg px-3 py-2"
      }
    >
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

  return slot ? createPortal(controls, slot) : controls;
}
