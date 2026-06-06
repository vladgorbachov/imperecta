import { create } from "zustand";
import {
  loadStoredDisplayCurrency,
  saveDisplayCurrency,
  type DisplayCurrency,
} from "@/lib/displayCurrency";

interface DisplayCurrencyState {
  displayCurrency: DisplayCurrency;
  setDisplayCurrency: (currency: DisplayCurrency) => void;
}

export const useDisplayCurrencyStore = create<DisplayCurrencyState>((set) => ({
  displayCurrency: loadStoredDisplayCurrency(),
  setDisplayCurrency: (currency) => {
    saveDisplayCurrency(currency);
    set({ displayCurrency: currency });
  },
}));
