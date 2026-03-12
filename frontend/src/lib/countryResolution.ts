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

/** Locale code to country code mapping. e.g. "ru" -> "RU", "en-US" -> "US" */
const LOCALE_MAP = new Map<string, string>([
  ["ru", "RU"],
  ["ru-RU", "RU"],
  ["uk", "UA"],
  ["uk-UA", "UA"],
  ["kk", "KZ"],
  ["kk-KZ", "KZ"],
  ["en", "US"],
  ["en-US", "US"],
  ["en-GB", "GB"],
  ["de", "DE"],
  ["de-DE", "DE"],
  ["fr", "FR"],
  ["fr-FR", "FR"],
  ["es", "ES"],
  ["es-ES", "ES"],
  ["it", "IT"],
  ["it-IT", "IT"],
  ["pt", "PT"],
  ["pt-PT", "PT"],
  ["pl", "PL"],
  ["pl-PL", "PL"],
  ["zh", "CN"],
  ["zh-CN", "CN"],
  ["ar", "AE"],
  ["ar-AE", "AE"],
  ["ro", "RO"],
  ["ro-RO", "RO"],
]);

const FALLBACK_COUNTRY = "US";

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
  if (savedCountry && getCountryByCode(savedCountry)) {
    return savedCountry.toUpperCase();
  }
  if (manualSelection && getCountryByCode(manualSelection)) {
    return manualSelection.toUpperCase();
  }
  const fromLocale = resolveCountryFromLocale(locale);
  return getCountryByCode(fromLocale) ? fromLocale : FALLBACK_COUNTRY;
}

export { FALLBACK_COUNTRY };
