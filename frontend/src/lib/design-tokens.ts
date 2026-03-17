/**
 * Design tokens for Imperecta.
 * Hex values used where CSS variables cannot be consumed (e.g. Recharts).
 */

/** Primary/accent color for "my price" line (sky-400, matches --accent) */
export const CHART_PRIMARY = "#38bdf8";

export const CHART_COLORS = [
  "#38bdf8",
  "#818cf8",
  "#34d399",
  "#fb923c",
  "#e879f9",
  "#fbbf24",
  "#94a3b8",
] as const;

export const CHART_COLORS_LIGHT = [
  "#0284c7",
  "#6366f1",
  "#059669",
  "#ea580c",
  "#a21caf",
  "#ca8a04",
  "#64748b",
] as const;

/** Marketplace colors: use hash from marketplace string. See MarketplaceBadge. */
export const MARKETPLACE_COLORS = {} as const;

export const BREAKPOINTS = {
  mobile: 768,
  tablet: 1024,
  desktop: 1280,
} as const;
