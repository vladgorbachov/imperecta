/**
 * Render-only cleanup for news provider source strings (semicolon/comma lists).
 */
export function formatNewsSource(raw: string): string | null {
  const seen = new Set<string>();
  const tokens: string[] = [];

  for (const part of raw.split(/[;,]/)) {
    const trimmed = part.trim();
    if (!trimmed) {
      continue;
    }
    if (trimmed.toLowerCase() === "feedloaderapi") {
      continue;
    }
    const key = trimmed.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    tokens.push(trimmed);
  }

  const cleaned = tokens.slice(0, 2).join(" · ");
  if (!cleaned || cleaned.toLowerCase() === "unknown") {
    return null;
  }
  return cleaned;
}
