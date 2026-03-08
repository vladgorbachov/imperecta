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

export const MARKETPLACE_COLORS = {
  ozon: { bg: "#005BFF", glow: "rgba(0,91,255,0.3)" },
  wildberries: { bg: "#CB11AB", glow: "rgba(203,17,171,0.3)" },
  kaspi: { bg: "#F14635", glow: "rgba(241,70,53,0.3)" },
  custom: { bg: "#64748b", glow: "rgba(100,116,139,0.3)" },
} as const;

export const BREAKPOINTS = {
  mobile: 768,
  tablet: 1024,
  desktop: 1280,
} as const;
