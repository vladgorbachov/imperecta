import { useTranslation } from "react-i18next";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  SUPPORTED_LANGUAGES,
  SUPPORTED_LANGUAGE_CODES,
  type LanguageCode,
} from "@/i18n";
import { authApi } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";

const STORAGE_KEY = "imperecta_language";

interface LanguageSelectorProps {
  value?: LanguageCode;
  onChange?: (code: LanguageCode) => void;
  showFlags?: boolean;
  /** Compact: flag + code only (e.g. "🇬🇧 en") */
  compact?: boolean;
}

export function LanguageSelector({
  value,
  onChange,
  showFlags = true,
  compact = false,
}: LanguageSelectorProps) {
  const { i18n } = useTranslation();

  const rawLang = value ?? i18n.language ?? "en";
  const resolved = rawLang.includes("-") ? rawLang.split("-")[0] : rawLang;
  const currentCode = (SUPPORTED_LANGUAGE_CODES.includes(resolved as LanguageCode)
    ? resolved
    : "en") as LanguageCode;
  const lang = SUPPORTED_LANGUAGES.find((l) => l.code === currentCode);
  const displayValue = compact
    ? `${lang?.flag ?? ""} ${currentCode}`
    : showFlags
      ? `${lang?.flag ?? ""} ${lang?.name ?? currentCode}`
      : lang?.name ?? currentCode;

  const handleChange = (code: string) => {
    const langCode = code as LanguageCode;
    i18n.changeLanguage(langCode);
    localStorage.setItem(STORAGE_KEY, langCode);
    onChange?.(langCode);
  };

  return (
    <Select value={currentCode} onValueChange={handleChange}>
      <SelectTrigger className={compact ? "h-8 w-16" : undefined}>
        <SelectValue>{displayValue}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {SUPPORTED_LANGUAGES.map((l) => (
          <SelectItem key={l.code} value={l.code}>
            {compact ? `${l.flag} ${l.code}` : showFlags ? `${l.flag} ${l.name}` : l.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function useLanguage() {
  const { i18n } = useTranslation();
  const accessToken = useAuthStore((s) => s.accessToken);
  const setUser = useAuthStore((s) => s.setUser);

  const currentLanguage =
    SUPPORTED_LANGUAGES.find((l) => l.code === i18n.language) ??
    SUPPORTED_LANGUAGES.find((l) => l.code === "en")!;

  const changeLanguage = async (code: LanguageCode) => {
    i18n.changeLanguage(code);
    localStorage.setItem(STORAGE_KEY, code);

    if (accessToken) {
      try {
        const { data } = await authApi.updateMe({ language: code });
        if (data) setUser(data);
      } catch {
        // Silently ignore API errors; local language change still applied
      }
    }
  };

  return {
    currentLanguage,
    changeLanguage,
    languages: SUPPORTED_LANGUAGES,
  };
}
