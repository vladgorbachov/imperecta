import type { FilterConfig } from "@/types/filters";

/**
 * Minimal filter config: price range only.
 * Brand/marketplace filters require API support for filter options.
 */
export const DEFAULT_FILTERS: FilterConfig[] = [
  {
    id: "price",
    labelKey: "filters.price",
    type: "range",
  },
];
