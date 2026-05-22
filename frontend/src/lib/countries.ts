/**
 * Europe + CIS countries only. Matches backend GET /api/markets/countries.
 * Display names are English fallback; use i18n (countries.CODE) for localized labels.
 */

export interface CountryInfo {
  code: string;
  name: string;
  name_local?: string;
  flag?: string;
  currency: string;
  region?: string;
}

/** Countries supported for Markets ticker. Europe + CIS. Alphabetical by English name. */
export const COUNTRIES: CountryInfo[] = [
  { code: "AM", name: "Armenia", name_local: "Армения", flag: "🇦🇲", currency: "AMD", region: "cis" },
  { code: "AZ", name: "Azerbaijan", name_local: "Азербайджан", flag: "🇦🇿", currency: "AZN", region: "cis" },
  { code: "GE", name: "Georgia", name_local: "Грузия", flag: "🇬🇪", currency: "GEL", region: "cis" },
  { code: "KZ", name: "Kazakhstan", name_local: "Казахстан", flag: "🇰🇿", currency: "KZT", region: "cis" },
  { code: "KG", name: "Kyrgyzstan", name_local: "Кыргызстан", flag: "🇰🇬", currency: "KGS", region: "cis" },
  { code: "MD", name: "Moldova", name_local: "Молдова", flag: "🇲🇩", currency: "MDL", region: "cis" },
  { code: "TJ", name: "Tajikistan", name_local: "Таджикистан", flag: "🇹🇯", currency: "TJS", region: "cis" },
  { code: "TM", name: "Turkmenistan", name_local: "Туркменистан", flag: "🇹🇲", currency: "TMT", region: "cis" },
  { code: "UA", name: "Ukraine", name_local: "Украина", flag: "🇺🇦", currency: "UAH", region: "cis" },
  { code: "UZ", name: "Uzbekistan", name_local: "Узбекистан", flag: "🇺🇿", currency: "UZS", region: "cis" },
  { code: "AL", name: "Albania", name_local: "Албания", flag: "🇦🇱", currency: "ALL", region: "europe" },
  { code: "AD", name: "Andorra", name_local: "Андорра", flag: "🇦🇩", currency: "EUR", region: "europe" },
  { code: "AT", name: "Austria", name_local: "Австрия", flag: "🇦🇹", currency: "EUR", region: "europe" },
  { code: "BE", name: "Belgium", name_local: "Бельгия", flag: "🇧🇪", currency: "EUR", region: "europe" },
  { code: "BA", name: "Bosnia and Herzegovina", name_local: "Босния", flag: "🇧🇦", currency: "BAM", region: "europe" },
  { code: "BG", name: "Bulgaria", name_local: "Болгария", flag: "🇧🇬", currency: "BGN", region: "europe" },
  { code: "HR", name: "Croatia", name_local: "Хорватия", flag: "🇭🇷", currency: "EUR", region: "europe" },
  { code: "CY", name: "Cyprus", name_local: "Кипр", flag: "🇨🇾", currency: "EUR", region: "europe" },
  { code: "CZ", name: "Czech Republic", name_local: "Чехия", flag: "🇨🇿", currency: "CZK", region: "europe" },
  { code: "DK", name: "Denmark", name_local: "Дания", flag: "🇩🇰", currency: "DKK", region: "europe" },
  { code: "EE", name: "Estonia", name_local: "Эстония", flag: "🇪🇪", currency: "EUR", region: "europe" },
  { code: "FI", name: "Finland", name_local: "Финляндия", flag: "🇫🇮", currency: "EUR", region: "europe" },
  { code: "FR", name: "France", name_local: "Франция", flag: "🇫🇷", currency: "EUR", region: "europe" },
  { code: "DE", name: "Germany", name_local: "Германия", flag: "🇩🇪", currency: "EUR", region: "europe" },
  { code: "GR", name: "Greece", name_local: "Греция", flag: "🇬🇷", currency: "EUR", region: "europe" },
  { code: "HU", name: "Hungary", name_local: "Венгрия", flag: "🇭🇺", currency: "HUF", region: "europe" },
  { code: "IS", name: "Iceland", name_local: "Исландия", flag: "🇮🇸", currency: "ISK", region: "europe" },
  { code: "IE", name: "Ireland", name_local: "Ирландия", flag: "🇮🇪", currency: "EUR", region: "europe" },
  { code: "IT", name: "Italy", name_local: "Италия", flag: "🇮🇹", currency: "EUR", region: "europe" },
  { code: "XK", name: "Kosovo", name_local: "Косово", flag: "🇽🇰", currency: "EUR", region: "europe" },
  { code: "LV", name: "Latvia", name_local: "Латвия", flag: "🇱🇻", currency: "EUR", region: "europe" },
  { code: "LI", name: "Liechtenstein", name_local: "Лихтенштейн", flag: "🇱🇮", currency: "CHF", region: "europe" },
  { code: "LT", name: "Lithuania", name_local: "Литва", flag: "🇱🇹", currency: "EUR", region: "europe" },
  { code: "LU", name: "Luxembourg", name_local: "Люксембург", flag: "🇱🇺", currency: "EUR", region: "europe" },
  { code: "MT", name: "Malta", name_local: "Мальта", flag: "🇲🇹", currency: "EUR", region: "europe" },
  { code: "ME", name: "Montenegro", name_local: "Черногория", flag: "🇲🇪", currency: "EUR", region: "europe" },
  { code: "NL", name: "Netherlands", name_local: "Нидерланды", flag: "🇳🇱", currency: "EUR", region: "europe" },
  { code: "MK", name: "North Macedonia", name_local: "Сев. Македония", flag: "🇲🇰", currency: "MKD", region: "europe" },
  { code: "NO", name: "Norway", name_local: "Норвегия", flag: "🇳🇴", currency: "NOK", region: "europe" },
  { code: "PL", name: "Poland", name_local: "Польша", flag: "🇵🇱", currency: "PLN", region: "europe" },
  { code: "PT", name: "Portugal", name_local: "Португалия", flag: "🇵🇹", currency: "EUR", region: "europe" },
  { code: "RO", name: "Romania", name_local: "Румыния", flag: "🇷🇴", currency: "RON", region: "europe" },
  { code: "RS", name: "Serbia", name_local: "Сербия", flag: "🇷🇸", currency: "RSD", region: "europe" },
  { code: "SK", name: "Slovakia", name_local: "Словакия", flag: "🇸🇰", currency: "EUR", region: "europe" },
  { code: "SI", name: "Slovenia", name_local: "Словения", flag: "🇸🇮", currency: "EUR", region: "europe" },
  { code: "ES", name: "Spain", name_local: "Испания", flag: "🇪🇸", currency: "EUR", region: "europe" },
  { code: "SE", name: "Sweden", name_local: "Швеция", flag: "🇸🇪", currency: "SEK", region: "europe" },
  { code: "CH", name: "Switzerland", name_local: "Швейцария", flag: "🇨🇭", currency: "CHF", region: "europe" },
  { code: "TR", name: "Turkey", name_local: "Турция", flag: "🇹🇷", currency: "TRY", region: "europe" },
  { code: "GB", name: "United Kingdom", name_local: "Великобритания", flag: "🇬🇧", currency: "GBP", region: "europe" },
];

const BY_CODE = new Map(COUNTRIES.map((c) => [c.code, c]));

export function getCountryByCode(code: string): CountryInfo | undefined {
  return BY_CODE.get(code.toUpperCase());
}

export function getCurrencyForCountry(code: string): string {
  if (code === "EUROPE") return "EUR";
  if (code === "CIS") return "RUB";
  return getCountryByCode(code)?.currency ?? "USD";
}
