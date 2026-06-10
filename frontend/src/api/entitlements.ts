import { apiClient } from "./client";

export interface UsageCounter {
  used: number;
  limit: number;
}

export interface EntitlementsUsage {
  products: UsageCounter;
}

export const entitlementsApi = {
  getUsage: () => apiClient.get<EntitlementsUsage>("/entitlements/usage"),
};

export const entitlementsQueryKeys = {
  all: ["entitlements"] as const,
  usage: () => [...entitlementsQueryKeys.all, "usage"] as const,
};
