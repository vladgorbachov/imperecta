/**
 * Script-safe normalization for multilingual country search.
 * Used by CountrySelector for search across Latin, Cyrillic, Arabic, Chinese.
 */

/** Normalize string for script-safe case-insensitive search. */
export function normalizeForSearch(s: string, locale: string): string {
  const trimmed = s.trim();
  if (!trimmed) return "";
  try {
    return trimmed.toLocaleLowerCase(locale);
  } catch {
    return trimmed.toLowerCase();
  }
}

export function matchesCountrySearch(
  label: string,
  code: string,
  searchTerm: string,
  locale: string
): boolean {
  const normQ = normalizeForSearch(searchTerm, locale);
  const normName = normalizeForSearch(label, locale);
  const normCode = normalizeForSearch(code, locale);
  return normName.includes(normQ) || normCode.includes(normQ);
}
