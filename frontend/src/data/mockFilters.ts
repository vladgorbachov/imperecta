import type { FilterConfig } from "@/types/filters";

const PRICE_RANGE_FILTER: FilterConfig = {
  id: "price",
  labelKey: "filters.price",
  type: "range",
};

const BASE_FILTERS: FilterConfig[] = [
  {
    id: "brand",
    labelKey: "filters.brand",
    type: "checkbox",
    options: [
      { value: "samsung", label: "Samsung", count: 142 },
      { value: "lg", label: "LG", count: 89 },
      { value: "sony", label: "Sony", count: 67 },
      { value: "philips", label: "Philips", count: 54 },
      { value: "bosch", label: "Bosch", count: 43 },
      { value: "xiaomi", label: "Xiaomi", count: 38 },
      { value: "asus", label: "Asus", count: 31 },
    ],
  },
  {
    id: "marketplace",
    labelKey: "filters.marketplace",
    type: "checkbox",
    options: [
      { value: "ozon", label: "Ozon", count: 234 },
      { value: "wildberries", label: "Wildberries", count: 198 },
      { value: "kaspi", label: "Kaspi", count: 87 },
    ],
  },
];

const ELECTRONICS_EXTRA: FilterConfig[] = [
  {
    id: "warranty",
    labelKey: "filters.warranty",
    type: "checkbox",
    options: [
      { value: "1y", label: "1 год", count: 45 },
      { value: "2y", label: "2 года", count: 89 },
      { value: "3y", label: "3 года", count: 23 },
    ],
  },
  {
    id: "condition",
    labelKey: "filters.condition",
    type: "checkbox",
    options: [
      { value: "new", label: "Новый", count: 198 },
      { value: "refurbished", label: "Восстановленный", count: 34 },
    ],
  },
];

export const MOCK_FILTERS_BY_CATEGORY: Record<string, FilterConfig[]> = {
  all: [PRICE_RANGE_FILTER, ...BASE_FILTERS],
  electronics: [PRICE_RANGE_FILTER, ...BASE_FILTERS, ...ELECTRONICS_EXTRA],
  appliances: [PRICE_RANGE_FILTER, ...BASE_FILTERS, ...ELECTRONICS_EXTRA],
  gadgets: [PRICE_RANGE_FILTER, ...BASE_FILTERS],
  accessories: [PRICE_RANGE_FILTER, ...BASE_FILTERS],
};
