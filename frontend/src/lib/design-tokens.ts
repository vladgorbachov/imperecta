/**
 * Design tokens for Imperecta.
 * Hex values used where CSS variables cannot be consumed (e.g. Recharts).
 */

/** Primary/accent color for "my price" line (teal, matches --primary) */
export const CHART_PRIMARY = "#0d9488";

/** 7 distinct chart line colors — avoid red/green (reserved for semantic price indicators) */
export const CHART_COLORS: string[] = [
  "#06b6d4", /* cyan */
  "#3b82f6", /* blue */
  "#8b5cf6", /* violet */
  "#f59e0b", /* amber */
  "#ec4899", /* pink */
  "#14b8a6", /* teal */
  "#0ea5e9", /* sky */
];

/** Marketplace brand colors for badges and indicators */
export const MARKETPLACE_COLORS: Record<"ozon" | "wildberries" | "kaspi" | "custom", string> = {
  ozon: "#f97316",
  wildberries: "#3b82f6",
  kaspi: "#dc2626",
  custom: "#64748b",
};

/** Breakpoints in pixels (mobile-first) */
export const BREAKPOINTS = {
  mobile: 0,
  tablet: 768,
  desktop: 1024,
} as const;
