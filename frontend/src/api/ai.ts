import { apiClient } from "./client";

/**
 * AI chat client. AI1 dropped the dead listSessions/getSession/deleteSession
 * exports; the live AIAnalystPage keeps message history in local React state.
 * Server-side session history will return alongside the future AI agent.
 */
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
};
