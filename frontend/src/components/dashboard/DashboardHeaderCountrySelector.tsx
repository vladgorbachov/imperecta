import { CountrySelector } from "@/components/dashboard/CountrySelector";
import { useDashboardCountryStore } from "@/stores/dashboardCountryStore";

/** Header-mounted country scope control; state is owned by the dashboard country store. */
export function DashboardHeaderCountrySelector() {
  const selectedCountry = useDashboardCountryStore((state) => state.selectedCountry);
  const setSelectedCountry = useDashboardCountryStore((state) => state.setSelectedCountry);
  const countryOptions = useDashboardCountryStore((state) => state.countryOptions);
  const optionsLoading = useDashboardCountryStore((state) => state.optionsLoading);

  return (
    <CountrySelector
      compact
      value={selectedCountry}
      onChange={setSelectedCountry}
      options={countryOptions}
      loading={optionsLoading}
    />
  );
}
