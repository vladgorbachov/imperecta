/**
 * Design tokens for Imperecta.
 * Hex values used where CSS variables cannot be consumed (e.g. Recharts).
 */

/** Primary/accent color for "my price" line (ice blue, matches --accent) */
export const CHART_PRIMARY = "#7fc3e8";

export const CHART_COLORS = [
  "#7fc3e8",
  "#98a2d4",
  "#6fc7a0",
  "#d9a06e",
  "#c793d6",
  "#d6bd7f",
  "#8b98a5",
] as const;

export const CHART_COLORS_LIGHT = [
  "#1878ad",
  "#5560b8",
  "#1a8f68",
  "#c07030",
  "#a355ad",
  "#a08520",
  "#6b7683",
] as const;

/** Marketplace colors: use hash from marketplace string. See MarketplaceBadge. */
export const MARKETPLACE_COLORS = {} as const;

export const BREAKPOINTS = {
  mobile: 768,
  tablet: 1024,
  desktop: 1280,
} as const;
