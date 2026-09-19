/**
 * Supported countries (bundled reference list; the backend dim_country is the
 * source of truth). Display names are the English fallback — localized labels
 * come from i18n (countries.CODE). Countries only, no grouping (2026-09-19).
 */

export interface CountryInfo {
  code: string;
  name: string;
  flag?: string;
  currency: string;
}

/** Alphabetical within the former CIS/Europe blocks; order is not semantic. */
export const COUNTRIES: CountryInfo[] = [
  { code: "AM", name: "Armenia", flag: "🇦🇲", currency: "AMD" },
  { code: "AZ", name: "Azerbaijan", flag: "🇦🇿", currency: "AZN" },
  { code: "GE", name: "Georgia", flag: "🇬🇪", currency: "GEL" },
  { code: "KG", name: "Kyrgyzstan", flag: "🇰🇬", currency: "KGS" },
  { code: "MD", name: "Moldova", flag: "🇲🇩", currency: "MDL" },
  { code: "TJ", name: "Tajikistan", flag: "🇹🇯", currency: "TJS" },
  { code: "TM", name: "Turkmenistan", flag: "🇹🇲", currency: "TMT" },
  { code: "UA", name: "Ukraine", flag: "🇺🇦", currency: "UAH" },
  { code: "UZ", name: "Uzbekistan", flag: "🇺🇿", currency: "UZS" },
  { code: "AL", name: "Albania", flag: "🇦🇱", currency: "ALL" },
  { code: "AD", name: "Andorra", flag: "🇦🇩", currency: "EUR" },
  { code: "AT", name: "Austria", flag: "🇦🇹", currency: "EUR" },
  { code: "BE", name: "Belgium", flag: "🇧🇪", currency: "EUR" },
  { code: "BA", name: "Bosnia and Herzegovina", flag: "🇧🇦", currency: "BAM" },
  { code: "BG", name: "Bulgaria", flag: "🇧🇬", currency: "BGN" },
  { code: "HR", name: "Croatia", flag: "🇭🇷", currency: "EUR" },
  { code: "CY", name: "Cyprus", flag: "🇨🇾", currency: "EUR" },
  { code: "CZ", name: "Czech Republic", flag: "🇨🇿", currency: "CZK" },
  { code: "DK", name: "Denmark", flag: "🇩🇰", currency: "DKK" },
  { code: "EE", name: "Estonia", flag: "🇪🇪", currency: "EUR" },
  { code: "FI", name: "Finland", flag: "🇫🇮", currency: "EUR" },
  { code: "FR", name: "France", flag: "🇫🇷", currency: "EUR" },
  { code: "DE", name: "Germany", flag: "🇩🇪", currency: "EUR" },
  { code: "GR", name: "Greece", flag: "🇬🇷", currency: "EUR" },
  { code: "HU", name: "Hungary", flag: "🇭🇺", currency: "HUF" },
  { code: "IS", name: "Iceland", flag: "🇮🇸", currency: "ISK" },
  { code: "IE", name: "Ireland", flag: "🇮🇪", currency: "EUR" },
  { code: "IT", name: "Italy", flag: "🇮🇹", currency: "EUR" },
  { code: "XK", name: "Kosovo", flag: "🇽🇰", currency: "EUR" },
  { code: "LV", name: "Latvia", flag: "🇱🇻", currency: "EUR" },
  { code: "LI", name: "Liechtenstein", flag: "🇱🇮", currency: "CHF" },
  { code: "LT", name: "Lithuania", flag: "🇱🇹", currency: "EUR" },
  { code: "LU", name: "Luxembourg", flag: "🇱🇺", currency: "EUR" },
  { code: "MT", name: "Malta", flag: "🇲🇹", currency: "EUR" },
  { code: "ME", name: "Montenegro", flag: "🇲🇪", currency: "EUR" },
  { code: "NL", name: "Netherlands", flag: "🇳🇱", currency: "EUR" },
  { code: "MK", name: "North Macedonia", flag: "🇲🇰", currency: "MKD" },
  { code: "NO", name: "Norway", flag: "🇳🇴", currency: "NOK" },
  { code: "PL", name: "Poland", flag: "🇵🇱", currency: "PLN" },
  { code: "PT", name: "Portugal", flag: "🇵🇹", currency: "EUR" },
  { code: "RO", name: "Romania", flag: "🇷🇴", currency: "RON" },
  { code: "RS", name: "Serbia", flag: "🇷🇸", currency: "RSD" },
  { code: "SK", name: "Slovakia", flag: "🇸🇰", currency: "EUR" },
  { code: "SI", name: "Slovenia", flag: "🇸🇮", currency: "EUR" },
  { code: "ES", name: "Spain", flag: "🇪🇸", currency: "EUR" },
  { code: "SE", name: "Sweden", flag: "🇸🇪", currency: "SEK" },
  { code: "CH", name: "Switzerland", flag: "🇨🇭", currency: "CHF" },
  { code: "TR", name: "Turkey", flag: "🇹🇷", currency: "TRY" },
  { code: "GB", name: "United Kingdom", flag: "🇬🇧", currency: "GBP" },
];

const BY_CODE = new Map(COUNTRIES.map((c) => [c.code, c]));

export function getCountryByCode(code: string): CountryInfo | undefined {
  return BY_CODE.get(code.toUpperCase());
}

export function getCurrencyForCountry(code: string): string {
  return getCountryByCode(code)?.currency ?? "EUR";
}
