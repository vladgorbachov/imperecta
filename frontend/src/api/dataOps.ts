/**
 * Client for the Rust data-ops read service (P6, docs/P6_FRONTEND_SPEC.md).
 * Separate origin from the main API; same Bearer JWT (shared HS256 secret).
 * Read-only and latency-sensitive, so no refresh dance here: on 401 the
 * query simply errors and recovers on the next retry once the main client
 * has refreshed the token.
 */

import axios from "axios";
import { useAuthStore } from "@/stores/authStore";
import { getStoredToken } from "@/lib/authStorage";

const DATA_OPS_URL: string =
  import.meta.env.VITE_DATA_OPS_URL ??
  "https://data-ops-production-8962.up.railway.app";

export const dataOpsClient = axios.create({
  baseURL: `${DATA_OPS_URL}/v1`,
  headers: { "Content-Type": "application/json" },
});

dataOpsClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken ?? getStoredToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

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
};
