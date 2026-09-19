/**
 * Public crawler-policy endpoints (WP4/WP5 companion, F8).
 * POST /bot/opt-out is unauthenticated and rate-limited per IP (422 on a
 * malformed domain/e-mail, 429 when throttled); contract P18.
 */

import { publicClient } from "./client";

export interface BotOptOutPayload {
  /** Source domain the request is about, e.g. "shop.example". */
  domain: string;
  /** Contact address for the confirmation (WP5.3 field name). */
  contact_email: string;
  /** Optional, <= 2000 chars. */
  message?: string;
}

/** 202 Accepted. */
export interface BotOptOutResponse {
  request_id: string;
  status: "received" | string;
}

export const botApi = {
  optOut: (payload: BotOptOutPayload) =>
    publicClient.post<BotOptOutResponse>("/bot/opt-out", payload),
};
