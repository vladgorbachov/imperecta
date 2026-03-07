import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import HttpBackend from "i18next-http-backend";
import LanguageDetector from "i18next-browser-languagedetector";

export const SUPPORTED_LANGUAGES = [
  { code: "en", name: "English", flag: "🇬🇧", dir: "ltr" as const },
  { code: "ar", name: "العربية", flag: "🇸🇦", dir: "rtl" as const },
  { code: "es", name: "Español", flag: "🇪🇸", dir: "ltr" as const },
  { code: "zh", name: "中文", flag: "🇨🇳", dir: "ltr" as const },
  { code: "ru", name: "Русский", flag: "🇷🇺", dir: "ltr" as const },
  { code: "fr", name: "Français", flag: "🇫🇷", dir: "ltr" as const },
] as const;

export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]["code"];

export const SUPPORTED_LANGUAGE_CODES = SUPPORTED_LANGUAGES.map((l) => l.code);

const STORAGE_KEY = "imperecta_language";

i18n
  .use(HttpBackend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: "en",
    supportedLngs: SUPPORTED_LANGUAGE_CODES,
    nonExplicitSupportedLngs: false,

    detection: {
      order: ["localStorage", "htmlTag"],
      lookupLocalStorage: STORAGE_KEY,
      caches: ["localStorage"],
    },

    backend: {
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

export default i18n;
