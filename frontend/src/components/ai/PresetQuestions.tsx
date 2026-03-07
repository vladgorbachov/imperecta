/**
 * Grid of preset question buttons for empty chat.
 */

import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

const PRESET_KEYS = [
  "ai.preset1",
  "ai.preset2",
  "ai.preset3",
  "ai.preset4",
  "ai.preset5",
  "ai.preset6",
] as const;

interface PresetQuestionsProps {
  /** question: translated text for display, presetKey: i18n key for mock lookup */
  onSelect: (question: string, presetKey: string) => void;
  className?: string;
}

export function PresetQuestions({ onSelect, className }: PresetQuestionsProps) {
  const { t } = useTranslation();

  return (
    <div className={cn("grid grid-cols-1 gap-3 sm:grid-cols-2", className)}>
      {PRESET_KEYS.map((key) => (
        <button
          key={key}
          type="button"
          onClick={() => onSelect(t(key), key)}
          className="rounded-xl border border-border/50 bg-card/60 px-4 py-3 text-left text-sm transition-colors hover:bg-accent/20 hover:border-primary/30 dark:border-border/50 dark:bg-card/60 dark:hover:bg-accent/20"
        >
          {t(key)}
        </button>
      ))}
    </div>
  );
}
