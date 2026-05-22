/**
 * Country resolution for Markets page. Priority order:
 * 1. Saved country (user preferences)
 * 2. Manual selection (in-session)
 * 3. Locale/timezone (i18n language)
 * 4. IP (not implemented - requires backend)
 * 5. Geolocation (optional, not required for normal use)
 *
 * Fallback: US when resolution fails.
 */

import { getCountryByCode } from "./countries";

/** Locale code to country code mapping. e.g. "ru" -> "UA", "en-US" -> "EUROPE" */
const LOCALE_MAP = new Map<string, string>([
  ["ru", "UA"],
  ["ru-RU", "UA"],
  ["uk", "UA"],
  ["uk-UA", "UA"],
  ["kk", "KZ"],
  ["kk-KZ", "KZ"],
  ["de", "DE"],
  ["de-DE", "DE"],
  ["pl", "PL"],
  ["pl-PL", "PL"],
  ["en", "EUROPE"],
  ["en-US", "EUROPE"],
  ["en-GB", "GB"],
  ["fr", "FR"],
  ["fr-FR", "FR"],
  ["es", "ES"],
  ["es-ES", "ES"],
  ["it", "IT"],
  ["it-IT", "IT"],
  ["pt", "PT"],
  ["pt-PT", "PT"],
  ["zh", "EUROPE"],
  ["zh-CN", "EUROPE"],
  ["ar", "EUROPE"],
  ["ar-AE", "EUROPE"],
  ["ro", "RO"],
  ["ro-RO", "RO"],
]);

const FALLBACK_COUNTRY = "EUROPE";

/**
 * Resolve country from locale (i18n language).
 * Does not use cookies, IP, or geolocation.
 */
export function resolveCountryFromLocale(locale: string): string {
  const normalized = locale.split("-")[0].toLowerCase();
  const full = locale.replace("_", "-");
  return LOCALE_MAP.get(full) ?? LOCALE_MAP.get(normalized) ?? FALLBACK_COUNTRY;
}

/**
 * Full resolution: saved > manual > locale > fallback.
 * IP and geolocation are not used (per requirements).
 */
export function resolveActiveCountry(
  savedCountry: string | null,
  manualSelection: string | null,
  locale: string
): string {
  if (savedCountry) {
    const upper = savedCountry.toUpperCase();
    if (upper === "EUROPE" || upper === "CIS" || getCountryByCode(upper)) return upper;
  }
  if (manualSelection) {
    const upper = manualSelection.toUpperCase();
    if (upper === "EUROPE" || upper === "CIS" || getCountryByCode(upper)) return upper;
  }
  const fromLocale = resolveCountryFromLocale(locale);
  return fromLocale === "EUROPE" || fromLocale === "CIS" || getCountryByCode(fromLocale)
    ? fromLocale
    : FALLBACK_COUNTRY;
}

export { FALLBACK_COUNTRY };
