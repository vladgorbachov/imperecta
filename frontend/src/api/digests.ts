import { apiClient } from "./client";

export const digestsApi = {
  list: () => apiClient.get("/digests"),
  get: (id: number) => apiClient.get(`/digests/${id}`),
};
