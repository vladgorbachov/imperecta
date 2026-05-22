import { useEffect } from "react";

export interface LanguageDescriptor {
  code: string;
  name: string;
  flag: string;
  dir: "ltr" | "rtl";
}

export interface TranslationCoverageResult {
  baseLanguage: string;
  totalBaseKeys: number;
  missingByLanguage: Record<string, string[]>;
  hasMissingKeys: boolean;
}

export type TranslationResourceMap = Record<string, Record<string, unknown>>;

const DEFAULT_ADMIN_ONLY_LANGUAGE_CODES = new Set(["ru"]);

/**
 * Returns language options available for the current user role.
 * Admin-only language codes are configurable for future policy changes.
 */
export function getLanguagesForUser(
  supportedLanguages: readonly LanguageDescriptor[],
  isAdmin: boolean,
  adminOnlyLanguageCodes: ReadonlySet<string> = DEFAULT_ADMIN_ONLY_LANGUAGE_CODES,
): LanguageDescriptor[] {
  if (isAdmin) return [...supportedLanguages];
  return supportedLanguages.filter((language) => !adminOnlyLanguageCodes.has(language.code));
}

/**
 * Flattens nested translation dictionaries to dot-based key paths.
 * Supports flat files as well as nested structures.
 */
export function flattenTranslationKeys(
  value: unknown,
  prefix = "",
  out: Set<string> = new Set(),
): Set<string> {
  if (!value || typeof value !== "object") return out;
  const entries = Object.entries(value as Record<string, unknown>);

  for (const [key, child] of entries) {
    const nextPrefix = prefix ? `${prefix}.${key}` : key;
    if (child && typeof child === "object" && !Array.isArray(child)) {
      flattenTranslationKeys(child, nextPrefix, out);
      continue;
    }
    out.add(nextPrefix);
  }

  return out;
}

/**
 * Validates that all keys from the base language exist in every target language.
 */
export function validateTranslationCoverage(
  resources: TranslationResourceMap,
  baseLanguage: string,
  targetLanguages: readonly string[],
): TranslationCoverageResult {
  const baseKeys = flattenTranslationKeys(resources[baseLanguage] ?? {});
  const missingByLanguage: Record<string, string[]> = {};

  for (const languageCode of targetLanguages) {
    const languageKeys = flattenTranslationKeys(resources[languageCode] ?? {});
    const missing = [...baseKeys].filter((key) => !languageKeys.has(key)).sort();
    missingByLanguage[languageCode] = missing;
  }

  const hasMissingKeys = Object.values(missingByLanguage).some((keys) => keys.length > 0);
  return {
    baseLanguage,
    totalBaseKeys: baseKeys.size,
    missingByLanguage,
    hasMissingKeys,
  };
}

/**
 * Checks a single translation key against multiple language resources.
 * Useful when registering brand-new UI elements in development mode.
 */
export function findMissingLanguagesForKey(
  resources: TranslationResourceMap,
  key: string,
  languagesToCheck: readonly string[],
): string[] {
  return languagesToCheck.filter((languageCode) => {
    const keys = flattenTranslationKeys(resources[languageCode] ?? {});
    return !keys.has(key);
  });
}

/**
 * Throws in development when key is missing in any required language.
 * In non-development environments this function is intentionally silent.
 */
export function assertTranslationKey(
  key: string,
  resources: TranslationResourceMap,
  requiredLanguageCodes: readonly string[],
): void {
  if (!import.meta.env.DEV) return;

  const missingLanguages = findMissingLanguagesForKey(resources, key, requiredLanguageCodes);
  if (missingLanguages.length === 0) return;

  const message =
    `[i18n-guard] Missing key "${key}" in languages: ${missingLanguages.join(", ")}. ` +
    "Add this key to every public locale before shipping.";
  throw new Error(message);
}

/**
 * React hook helper for registering keys used by a component.
 * Recommended usage:
 * useTranslationGuard(["dashboard.title", "dashboard.subtitle"], resources, publicLanguageCodes)
 */
export function useTranslationGuard(
  keys: readonly string[],
  resources: TranslationResourceMap,
  requiredLanguageCodes: readonly string[],
): void {
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    for (const key of keys) {
      assertTranslationKey(key, resources, requiredLanguageCodes);
    }
  }, [keys, resources, requiredLanguageCodes]);
}

