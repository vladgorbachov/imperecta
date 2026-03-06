/**
 * Filter types for ProductsPage filters panel.
 */

export interface FilterOption {
  value: string;
  label: string;
  count?: number;
}

export interface FilterConfig {
  id: string;
  labelKey: string;
  type: "checkbox" | "range" | "select";
  options?: FilterOption[];
}
