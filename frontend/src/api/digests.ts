import { apiClient } from "./client";

export interface Digest {
  id: string;
  period_type: string;
  period_start: string;
  period_end: string;
  content_md: string;
  sent_at: string | null;
  created_at: string;
}

export const digestsApi = {
  list: () => apiClient.get<Digest[]>("/digests"),
  get: (id: string) => apiClient.get<Digest>(`/digests/${id}`),
};
