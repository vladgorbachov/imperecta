import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import HttpBackend from "i18next-http-backend";
import LanguageDetector from "i18next-browser-languagedetector";

export const SUPPORTED_LANGUAGES = [
  { code: "ru", name: "Русский", flag: "🇷🇺", region: "cis" },
  { code: "uk", name: "Українська", flag: "🇺🇦", region: "cis" },
  { code: "be", name: "Беларуская", flag: "🇧🇾", region: "cis" },
  { code: "kk", name: "Қазақша", flag: "🇰🇿", region: "cis" },
  { code: "uz", name: "Oʻzbekcha", flag: "🇺🇿", region: "cis" },
  { code: "ky", name: "Кыргызча", flag: "🇰🇬", region: "cis" },
  { code: "tg", name: "Тоҷикӣ", flag: "🇹🇯", region: "cis" },
  { code: "tk", name: "Türkmençe", flag: "🇹🇲", region: "cis" },
  { code: "az", name: "Azərbaycanca", flag: "🇦🇿", region: "cis" },
  { code: "hy", name: "Հայերեն", flag: "🇦🇲", region: "cis" },
  { code: "ka", name: "ქართული", flag: "🇬🇪", region: "cis" },
  { code: "ro", name: "Română", flag: "🇷🇴", region: "cis" },
  { code: "en", name: "English", flag: "🇬🇧", region: "europe" },
  { code: "de", name: "Deutsch", flag: "🇩🇪", region: "europe" },
  { code: "fr", name: "Français", flag: "🇫🇷", region: "europe" },
  { code: "es", name: "Español", flag: "🇪🇸", region: "europe" },
  { code: "it", name: "Italiano", flag: "🇮🇹", region: "europe" },
  { code: "pt", name: "Português", flag: "🇵🇹", region: "europe" },
  { code: "nl", name: "Nederlands", flag: "🇳🇱", region: "europe" },
  { code: "pl", name: "Polski", flag: "🇵🇱", region: "europe" },
  { code: "cs", name: "Čeština", flag: "🇨🇿", region: "europe" },
  { code: "sk", name: "Slovenčina", flag: "🇸🇰", region: "europe" },
  { code: "hu", name: "Magyar", flag: "🇭🇺", region: "europe" },
  { code: "bg", name: "Български", flag: "🇧🇬", region: "europe" },
  { code: "hr", name: "Hrvatski", flag: "🇭🇷", region: "europe" },
  { code: "sr", name: "Српски", flag: "🇷🇸", region: "europe" },
  { code: "sl", name: "Slovenščina", flag: "🇸🇮", region: "europe" },
  { code: "mk", name: "Македонски", flag: "🇲🇰", region: "europe" },
  { code: "sq", name: "Shqip", flag: "🇦🇱", region: "europe" },
  { code: "el", name: "Ελληνικά", flag: "🇬🇷", region: "europe" },
  { code: "tr", name: "Türkçe", flag: "🇹🇷", region: "europe" },
  { code: "fi", name: "Suomi", flag: "🇫🇮", region: "europe" },
  { code: "sv", name: "Svenska", flag: "🇸🇪", region: "europe" },
  { code: "no", name: "Norsk", flag: "🇳🇴", region: "europe" },
  { code: "da", name: "Dansk", flag: "🇩🇰", region: "europe" },
  { code: "et", name: "Eesti", flag: "🇪🇪", region: "europe" },
  { code: "lv", name: "Latviešu", flag: "🇱🇻", region: "europe" },
  { code: "lt", name: "Lietuvių", flag: "🇱🇹", region: "europe" },
  { code: "ga", name: "Gaeilge", flag: "🇮🇪", region: "europe" },
  { code: "is", name: "Íslenska", flag: "🇮🇸", region: "europe" },
  { code: "mt", name: "Malti", flag: "🇲🇹", region: "europe" },
  { code: "bs", name: "Bosanski", flag: "🇧🇦", region: "europe" },
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
      order: ["localStorage", "navigator", "htmlTag"],
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

const setHtmlLang = (lng: string) => {
  if (typeof document !== "undefined") {
    document.documentElement.lang = lng || "en";
  }
};

i18n.on("languageChanged", setHtmlLang);
i18n.on("initialized", () => setHtmlLang(i18n.language));

export default i18n;
