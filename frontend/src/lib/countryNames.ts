/**
 * Country code to i18n key mapping.
 * Display names come from translation files: countries.AE, countries.US, etc.
 * Fallback to English name when key missing.
 */

import { COUNTRIES } from "./countries";

/** English fallback names (used when translation key missing). */
export const COUNTRY_NAMES_EN: Record<string, string> = {
  ...Object.fromEntries(COUNTRIES.map((c) => [c.code, c.name])),
  EUROPE: "Europe",
  CIS: "CIS",
};

export const COUNTRY_CODES = COUNTRIES.map((c) => c.code);
