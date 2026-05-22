import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import HttpBackend from "i18next-http-backend";
import LanguageDetector from "i18next-browser-languagedetector";
import {
  getLanguagesForUser,
  validateTranslationCoverage,
  type LanguageDescriptor,
  type TranslationResourceMap,
} from "./translationGuard";

export const SUPPORTED_LANGUAGES = [
  { code: "en", name: "English", flag: "🇬🇧", dir: "ltr" as const },
  { code: "ar", name: "العربية", flag: "🇸🇦", dir: "rtl" as const },
  { code: "es", name: "Español", flag: "🇪🇸", dir: "ltr" as const },
  { code: "zh", name: "中文", flag: "🇨🇳", dir: "ltr" as const },
  { code: "ru", name: "Русский", flag: "🇷🇺", dir: "ltr" as const },
  { code: "fr", name: "Français", flag: "🇫🇷", dir: "ltr" as const },
  { code: "ro", name: "Română", flag: "🇷🇴", dir: "ltr" as const },
  { code: "uk", name: "Українська", flag: "🇺🇦", dir: "ltr" as const },
] as const;

export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]["code"];

export const SUPPORTED_LANGUAGE_CODES = SUPPORTED_LANGUAGES.map((l) => l.code);
export const PUBLIC_LANGUAGES = getLanguagesForUser(
  SUPPORTED_LANGUAGES as readonly LanguageDescriptor[],
  false,
);
export const PUBLIC_LANGUAGE_CODES = PUBLIC_LANGUAGES.map((language) => language.code);

const STORAGE_KEY = "imperecta_language";
const IS_VITEST = Boolean(import.meta.env.VITEST);

const i18nBuilder = i18n.use(initReactI18next);
if (!IS_VITEST) {
  i18nBuilder.use(HttpBackend).use(LanguageDetector);
}

i18nBuilder.init({
    fallbackLng: "en",
    supportedLngs: SUPPORTED_LANGUAGE_CODES,
    nonExplicitSupportedLngs: false,

    detection: IS_VITEST
      ? undefined
      : {
          order: ["localStorage", "htmlTag"],
          lookupLocalStorage: STORAGE_KEY,
          caches: ["localStorage"],
        },

    backend: IS_VITEST
      ? undefined
      : {
          loadPath: "/locales/{{lng}}/translation.json",
        },

    interpolation: {
      escapeValue: false,
    },

    react: {
      useSuspense: true,
    },
  });

i18n.on("languageChanged", (lng) => {
  const dir = SUPPORTED_LANGUAGES.find((l) => l.code === lng)?.dir ?? "ltr";
  document.documentElement.dir = dir;
  document.documentElement.lang = lng;
});

i18n.on("initialized", () => {
  enforceLanguagePolicy(false);
  const lng = i18n.language;
  const dir = SUPPORTED_LANGUAGES.find((l) => l.code === lng)?.dir ?? "ltr";
  document.documentElement.dir = dir;
  document.documentElement.lang = lng;
});

/**
 * Enforce language access policy based on admin privileges.
 * Non-admin users cannot keep Russian UI.
 */
export function enforceLanguagePolicy(isAdmin: boolean): void {
  const persisted = localStorage.getItem(STORAGE_KEY) ?? "";
  const activeLanguage = (persisted || i18n.resolvedLanguage || i18n.language || "").toLowerCase();
  const isRussianLanguage = activeLanguage === "ru" || activeLanguage.startsWith("ru-");

  if (!isAdmin && isRussianLanguage) {
    if (!import.meta.env.VITEST) {
      i18n.changeLanguage("en");
    }
    localStorage.setItem(STORAGE_KEY, "en");
  }
}

/**
 * Returns locale options based on role policy.
 * Russian remains admin-only by business rule.
 */
export function getAvailableLanguages(isAdmin: boolean): readonly LanguageDescriptor[] {
  return getLanguagesForUser(
    SUPPORTED_LANGUAGES as readonly LanguageDescriptor[],
    isAdmin,
  );
}

async function loadLocaleResource(languageCode: string): Promise<Record<string, unknown>> {
  const response = await fetch(`/locales/${languageCode}/translation.json`);
  if (!response.ok) {
    throw new Error(`Failed to load translation file for ${languageCode}: ${response.status}`);
  }
  return (await response.json()) as Record<string, unknown>;
}

/**
 * Development-only audit:
 * ensures every key from base language exists in all public languages.
 */
export async function runTranslationCoverageAudit(): Promise<void> {
  if (!import.meta.env.DEV || import.meta.env.VITEST) return;

  const resources: TranslationResourceMap = {};
  for (const languageCode of PUBLIC_LANGUAGE_CODES) {
    resources[languageCode] = await loadLocaleResource(languageCode);
  }

  const coverage = validateTranslationCoverage(resources, "en", PUBLIC_LANGUAGE_CODES);
  if (!coverage.hasMissingKeys) return;

  const diagnostics = Object.entries(coverage.missingByLanguage)
    .filter(([, missing]) => missing.length > 0)
    .map(([language, missing]) => `${language}: ${missing.slice(0, 10).join(", ")}`)
    .join(" | ");
  throw new Error(`[i18n-guard] Missing public translations detected: ${diagnostics}`);
}

if (import.meta.env.DEV && !import.meta.env.VITEST) {
  void runTranslationCoverageAudit().catch((error) => {
    console.error(error);
  });
}

export default i18n;
