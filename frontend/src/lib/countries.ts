/**
 * ISO 3166-1 alpha-2 country codes with display names and local currency.
 * Used for country selector and ticker bar FX/fuel prioritization.
 */

export interface CountryInfo {
  code: string;
  name: string;
  currency: string;
}

/** Countries supported for Markets ticker. Sorted alphabetically by name. */
export const COUNTRIES: CountryInfo[] = [
  { code: "AE", name: "United Arab Emirates", currency: "AED" },
  { code: "AR", name: "Argentina", currency: "ARS" },
  { code: "AT", name: "Austria", currency: "EUR" },
  { code: "AU", name: "Australia", currency: "AUD" },
  { code: "BE", name: "Belgium", currency: "EUR" },
  { code: "BG", name: "Bulgaria", currency: "BGN" },
  { code: "BR", name: "Brazil", currency: "BRL" },
  { code: "BY", name: "Belarus", currency: "BYN" },
  { code: "CA", name: "Canada", currency: "CAD" },
  { code: "CH", name: "Switzerland", currency: "CHF" },
  { code: "CN", name: "China", currency: "CNY" },
  { code: "CZ", name: "Czech Republic", currency: "CZK" },
  { code: "DE", name: "Germany", currency: "EUR" },
  { code: "ES", name: "Spain", currency: "EUR" },
  { code: "FR", name: "France", currency: "EUR" },
  { code: "GB", name: "United Kingdom", currency: "GBP" },
  { code: "GE", name: "Georgia", currency: "GEL" },
  { code: "GR", name: "Greece", currency: "EUR" },
  { code: "HU", name: "Hungary", currency: "HUF" },
  { code: "IN", name: "India", currency: "INR" },
  { code: "IT", name: "Italy", currency: "EUR" },
  { code: "JP", name: "Japan", currency: "JPY" },
  { code: "KZ", name: "Kazakhstan", currency: "KZT" },
  { code: "LT", name: "Lithuania", currency: "EUR" },
  { code: "LV", name: "Latvia", currency: "EUR" },
  { code: "MD", name: "Moldova", currency: "MDL" },
  { code: "MX", name: "Mexico", currency: "MXN" },
  { code: "NL", name: "Netherlands", currency: "EUR" },
  { code: "PL", name: "Poland", currency: "PLN" },
  { code: "PT", name: "Portugal", currency: "EUR" },
  { code: "RO", name: "Romania", currency: "RON" },
  { code: "RU", name: "Russia", currency: "RUB" },
  { code: "SE", name: "Sweden", currency: "SEK" },
  { code: "TR", name: "Turkey", currency: "TRY" },
  { code: "UA", name: "Ukraine", currency: "UAH" },
  { code: "US", name: "United States", currency: "USD" },
  { code: "UZ", name: "Uzbekistan", currency: "UZS" },
];

const BY_CODE = new Map(COUNTRIES.map((c) => [c.code, c]));

export function getCountryByCode(code: string): CountryInfo | undefined {
  return BY_CODE.get(code.toUpperCase());
}

export function getCurrencyForCountry(code: string): string {
  return getCountryByCode(code)?.currency ?? "USD";
}
