/** Regional-indicator flag for any ISO 3166-1 alpha-2 code; empty for non-codes. */
export function flagForCode(code: string | null | undefined): string {
  const upper = (code ?? "").toUpperCase();
  if (!/^[A-Z]{2}$/.test(upper)) {
    return "";
  }
  return String.fromCodePoint(
    ...upper.split("").map((char) => 0x1f1e6 + char.charCodeAt(0) - 65),
  );
}
