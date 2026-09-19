/**
 * Public crawler-policy endpoints (WP4/WP5 companion, F8).
 * POST /bot/opt-out is unauthenticated and rate-limited on the backend; the
 * contract is proposed in FRONTEND_BACKEND_REQUESTS.md P18.
 */

import { publicClient } from "./client";

export interface BotOptOutPayload {
  /** Source domain the request is about, e.g. "shop.example". */
  domain: string;
  /** Contact address for the confirmation. */
  email: string;
  message?: string;
}

export interface BotOptOutResponse {
  /** Reference the requester can quote in follow-ups. */
  request_id?: string;
  status?: string;
}

export const botApi = {
  optOut: (payload: BotOptOutPayload) =>
    publicClient.post<BotOptOutResponse>("/bot/opt-out", payload),
};
