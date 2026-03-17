/**
 * Null-safe number formatting. Prevents "toFixed is not a function" crashes
 * when API returns null/undefined or non-numeric values.
 */

export function safeFixed(value: unknown, digits: number = 2): string {
  const num = typeof value === "number" ? value : parseFloat(String(value));
  if (isNaN(num) || !isFinite(num)) return "0";
  return num.toFixed(digits);
}

export function safeNumber(value: unknown): number {
  const num = typeof value === "number" ? value : parseFloat(String(value));
  return isNaN(num) || !isFinite(num) ? 0 : num;
}
