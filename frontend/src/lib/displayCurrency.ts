/**
 * Display currency modes for cross-marketplace price comparison.
 * Conversion is performed by the backend; the frontend only formats results.
 */

export const DISPLAY_CURRENCY_VALUES = ["local", "EUR", "USD"] as const;

export type DisplayCurrency = (typeof DISPLAY_CURRENCY_VALUES)[number];

export const DISPLAY_CURRENCY_STORAGE_KEY = "imperecta_display_currency";

/** Flip to true when backend supports display_currency and fills converted prices. */
export const DISPLAY_CURRENCY_BACKEND_SUPPORT: Record<
  Exclude<DisplayCurrency, "local">,
  boolean
> = {
  EUR: true,
  USD: true,
};

export interface DisplayCurrencyOption {
  value: DisplayCurrency;
  labelKey: string;
  hintKey: string;
}

export const DISPLAY_CURRENCY_OPTIONS: DisplayCurrencyOption[] = [
  { value: "local", labelKey: "displayCurrency.local", hintKey: "displayCurrency.localHint" },
  { value: "EUR", labelKey: "displayCurrency.eur", hintKey: "displayCurrency.eurHint" },
  { value: "USD", labelKey: "displayCurrency.usd", hintKey: "displayCurrency.usdHint" },
];

export function isDisplayCurrencyEnabled(value: DisplayCurrency): boolean {
  if (value === "local") {
    return true;
  }
  return DISPLAY_CURRENCY_BACKEND_SUPPORT[value];
}

export function loadStoredDisplayCurrency(): DisplayCurrency {
  try {
    const stored = localStorage.getItem(DISPLAY_CURRENCY_STORAGE_KEY);
    if (stored && DISPLAY_CURRENCY_VALUES.includes(stored as DisplayCurrency)) {
      const value = stored as DisplayCurrency;
      if (isDisplayCurrencyEnabled(value)) {
        return value;
      }
    }
  } catch {
    // localStorage unavailable
  }
  return "local";
}

export function saveDisplayCurrency(value: DisplayCurrency): void {
  try {
    localStorage.setItem(DISPLAY_CURRENCY_STORAGE_KEY, value);
  } catch {
    // localStorage unavailable
  }
}

export interface ConvertiblePriceFields {
  localAmount: number | null | undefined;
  localCurrency: string | null | undefined;
  displayAmount?: number | null;
  displayCurrency?: string | null;
  conversionAvailable?: boolean;
}

export interface ResolvedDisplayPrice {
  amount: number | null;
  currency: string | null;
  noRate: boolean;
}

/**
 * Resolves which amount/currency to show based on the selected display mode.
 * Falls back to local currency with noRate when conversion is unavailable.
 */
export function resolvePriceForDisplay(
  fields: ConvertiblePriceFields,
  mode: DisplayCurrency
): ResolvedDisplayPrice {
  if (fields.localAmount == null) {
    return { amount: null, currency: null, noRate: false };
  }

  if (mode === "local") {
    return {
      amount: fields.localAmount,
      currency: fields.localCurrency ?? null,
      noRate: false,
    };
  }

  const hasConversion =
    fields.conversionAvailable === true &&
    fields.displayAmount != null &&
    fields.displayCurrency != null;

  if (hasConversion) {
    return {
      amount: fields.displayAmount ?? null,
      currency: fields.displayCurrency ?? mode,
      noRate: false,
    };
  }

  return {
    amount: fields.localAmount,
    currency: fields.localCurrency ?? null,
    noRate: true,
  };
}
