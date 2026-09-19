/**
 * Legal document texts (F8). Counsel delivers the texts separately; until
 * then every registry entry is empty and the page shows an explicit
 * "text pending" notice — nothing is invented here. Structure per language:
 * ordered sections with an optional heading and plain-text paragraphs.
 */

import type { LanguageCode } from "@/i18n";

export type LegalPageKey = "terms" | "privacy" | "aup" | "data-sources";

export interface LegalSection {
  heading?: string;
  paragraphs: string[];
}

export type LegalText = Partial<Record<LanguageCode, LegalSection[]>>;

export const LEGAL_TEXTS: Record<LegalPageKey, LegalText> = {
  terms: {},
  privacy: {},
  aup: {},
  "data-sources": {},
};

/** English is the binding language; other locales fall back to it. */
export function resolveLegalText(page: LegalPageKey, language: string): LegalSection[] | null {
  const byLanguage = LEGAL_TEXTS[page];
  const short = language.split("-")[0] as LanguageCode;
  const sections = byLanguage[short] ?? byLanguage.en;
  return sections && sections.length > 0 ? sections : null;
}
