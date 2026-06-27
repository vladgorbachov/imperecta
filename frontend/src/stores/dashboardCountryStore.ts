import { create } from "zustand";
import type { CountrySelectorOption } from "@/components/dashboard/CountrySelector";

interface DashboardCountryState {
  selectedCountry: string | null;
  setSelectedCountry: (code: string | null) => void;
  countryOptions: CountrySelectorOption[];
  setCountryOptions: (options: CountrySelectorOption[]) => void;
  optionsLoading: boolean;
  setOptionsLoading: (loading: boolean) => void;
}

export const useDashboardCountryStore = create<DashboardCountryState>((set) => ({
  selectedCountry: null,
  setSelectedCountry: (code) => set({ selectedCountry: code }),
  countryOptions: [],
  setCountryOptions: (options) => set({ countryOptions: options }),
  optionsLoading: false,
  setOptionsLoading: (loading) => set({ optionsLoading: loading }),
}));
