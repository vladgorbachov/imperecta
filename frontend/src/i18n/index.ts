import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import HttpBackend from "i18next-http-backend";
import LanguageDetector from "i18next-browser-languagedetector";
import {
  validateTranslationCoverage,
  type LanguageDescriptor,
  type TranslationResourceMap,
} from "./translationGuard";

export const SUPPORTED_LANGUAGES = [
  { code: "en", name: "English", flag: "🇬🇧", dir: "ltr" as const },
  { code: "ar", name: "العربية", flag: "🇸🇦", dir: "rtl" as const },
  { code: "es", name: "Español", flag: "🇪🇸", dir: "ltr" as const },
  { code: "zh", name: "中文", flag: "🇨🇳", dir: "ltr" as const },
  { code: "fr", name: "Français", flag: "🇫🇷", dir: "ltr" as const },
  { code: "ro", name: "Română", flag: "🇷🇴", dir: "ltr" as const },
  { code: "uk", name: "Українська", flag: "🇺🇦", dir: "ltr" as const },
] as const;

export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]["code"];

export const SUPPORTED_LANGUAGE_CODES = SUPPORTED_LANGUAGES.map((l) => l.code);

export function isSupportedLanguage(code: string): code is LanguageCode {
  return (SUPPORTED_LANGUAGE_CODES as readonly string[]).includes(code);
}

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
  const lng = i18n.language;
  const dir = SUPPORTED_LANGUAGES.find((l) => l.code === lng)?.dir ?? "ltr";
  document.documentElement.dir = dir;
  document.documentElement.lang = lng;
});

/** Every supported language is public — no role-gated locales (WP11, 2026-09-19). */
export function getAvailableLanguages(): readonly LanguageDescriptor[] {
  return SUPPORTED_LANGUAGES as readonly LanguageDescriptor[];
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
 * ensures every key from base language exists in every supported language.
 */
export async function runTranslationCoverageAudit(): Promise<void> {
  if (!import.meta.env.DEV || import.meta.env.VITEST) return;

  const resources: TranslationResourceMap = {};
  for (const languageCode of SUPPORTED_LANGUAGE_CODES) {
    resources[languageCode] = await loadLocaleResource(languageCode);
  }

  const coverage = validateTranslationCoverage(resources, "en", SUPPORTED_LANGUAGE_CODES);
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
