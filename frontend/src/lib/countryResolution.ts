/**
 * Country resolution for Markets page.
 * Uses explicit values only (saved user preference or manual selection).
 */

import { getCountryByCode } from "./countries";

const BLOCKED_PUBLIC_COUNTRIES = new Set(["RU", "BY"]);

function isAllowedPublicCountry(code: string): boolean {
  if (BLOCKED_PUBLIC_COUNTRIES.has(code)) return false;
  return Boolean(getCountryByCode(code));
}

/**
 * Resolve country from locale (i18n language).
 * Does not use cookies, IP, or geolocation.
 */
export function resolveCountryFromLocale(locale: string): string {
  void locale;
  return "";
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
    if (isAllowedPublicCountry(upper)) return upper;
  }
  if (manualSelection) {
    const upper = manualSelection.toUpperCase();
    if (isAllowedPublicCountry(upper)) return upper;
  }
  const fromLocale = resolveCountryFromLocale(locale);
  return isAllowedPublicCountry(fromLocale) ? fromLocale : "";
}
