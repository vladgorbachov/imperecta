/**
 * Client for the Rust data-ops read service (P6, docs/P6_FRONTEND_SPEC.md).
 * Separate origin from the main API, same JWT: since WP2 every pool read is
 * user-scoped (no anonymous path, no edge cache), so the auth interceptors
 * from setupAuth.ts attach the Bearer token and handle 401 refresh here too.
 */

import axios from "axios";
import type { PoolProductItem, PoolProductsParams, PoolProductsResponse } from "./products";

const DATA_OPS_URL: string =
  import.meta.env.VITE_DATA_OPS_URL ??
  "https://data-ops-production-8962.up.railway.app";

export const dataOpsClient = axios.create({
  baseURL: `${DATA_OPS_URL}/v1`,
  headers: { Accept: "application/json" },
});

/** POST /v1/pool/products/refresh — live catch-up for on-screen rows. */
export interface PoolRefreshResponse {
  items: PoolProductItem[];
  refreshed_at: string;
}

/** Server-side cap on ids per refresh call. */
export const POOL_REFRESH_MAX_IDS = 500;

export type MatchMethod =
  | "gtin"
  | "brand_model"
  | "title_exact"
  | "title_sim"
  | "unmatched";

export interface ComparisonOffer {
  listing_id: string;
  product_id: string;
  marketplace_code: string;
  marketplace_name: string;
  country_code: string | null;
  name: string;
  title_en: string | null;
  external_url: string;
  last_price: number | null;
  last_currency_code: string | null;
  last_price_eur: number | null;
  last_checked_at: string | null;
  match_method: MatchMethod;
  match_confidence: number | null;
}

export interface ComparisonGroup {
  group_id: string;
  shops: number;
  min_price_eur: number | null;
  max_price_eur: number | null;
  /** Sorted last_price_eur ASC NULLS LAST; first priced offer = cheapest. */
  offers: ComparisonOffer[];
}

export interface ListingComparison {
  listing_id: string;
  match_method: MatchMethod | null;
  group: ComparisonGroup | null;
}

export const dataOpsApi = {
  getListingComparison: (listingId: string) =>
    dataOpsClient.get<ListingComparison>(`/listings/${listingId}/comparison`),

  getGroupOffers: (groupId: string) =>
    dataOpsClient.get<ComparisonGroup>(`/groups/${groupId}/offers`),

  /** R4 contract-parity port of /pool/products (same params + envelope). */
  fetchPoolProducts: (params: PoolProductsParams) =>
    dataOpsClient.get<PoolProductsResponse>("/pool/products", { params }),

  /** Current rows for the ids a page already shows (<= 500, never cached). */
  refreshPoolProducts: (ids: string[], displayCurrency?: string) =>
    dataOpsClient.post<PoolRefreshResponse>("/pool/products/refresh", {
      ids: ids.slice(0, POOL_REFRESH_MAX_IDS),
      display_currency: displayCurrency,
    }),
};
