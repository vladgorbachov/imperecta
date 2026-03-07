import { apiClient } from "./client";

export const aiApi = {
  chat: (data: {
    message: string;
    session_id?: number;
    context_type?: string;
    context_id?: string;
  }) =>
    apiClient.post<{
      session_id: number;
      response: string;
      tokens_used: number;
      duration_ms: number;
    }>("/ai/chat", data),
  listSessions: () =>
    apiClient.get<
      Array<{
        id: number;
        title: string | null;
        context_type: string | null;
        created_at: string;
        updated_at: string;
        message_count: number;
      }>
    >("/ai/sessions"),
  getSession: (sessionId: number) =>
    apiClient.get<{
      id: number;
      title: string | null;
      context_type: string | null;
      messages: Array<{ role: string; content: string; created_at: string }>;
    }>(`/ai/sessions/${sessionId}`),
  deleteSession: (sessionId: number) =>
    apiClient.delete(`/ai/sessions/${sessionId}`),
};
