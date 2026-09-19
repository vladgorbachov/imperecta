import { apiClient, publicClient } from "./client";
import type { AccountType, LegalDocument } from "@/lib/legalVersions";

export interface ConsentAcceptance {
  document: LegalDocument;
  version: string;
}

export interface UserConsent extends ConsentAcceptance {
  accepted_at: string;
}

export interface LegalDocumentInfo {
  version: string;
  url: string | null;
}

/** GET /legal/documents — keyed by document (WP6 contract, 2026-09-19). */
export type LegalDocumentsResponse = Record<LegalDocument, LegalDocumentInfo>;

/** Sibling of `detail` on 409 consent_required / 422 consent_version_outdated. */
export interface RequiredConsent {
  document: LegalDocument;
  version: string;
  url?: string | null;
}

export interface RegisterPayload {
  email: string;
  password: string;
  name: string;
  companyName?: string;
  language?: string;
  countryCode: string;
  accountType: AccountType;
  businessUseConfirmed: true;
  adultConfirmed: true;
  termsVersion: string;
  privacyVersion: string;
}

export const authApi = {
  login: (
    email: string,
    password: string,
    remember_me?: boolean,
    consents?: ConsentAcceptance[]
  ) =>
    apiClient.post<{
      access_token: string;
      refresh_token: string;
      persistent?: boolean;
      expires_at?: string;
      force_password_change?: boolean;
    }>("/auth/login", {
      email,
      password,
      remember_me: remember_me ?? false,
      ...(consents && consents.length > 0 ? { consents } : {}),
    }),
  refresh: (refresh_token: string) =>
    apiClient.post<{
      access_token: string;
      refresh_token: string;
      persistent?: boolean;
      expires_at?: string;
    }>("/auth/refresh", { refresh_token }),
  register: (payload: RegisterPayload) =>
    apiClient.post<{
      access_token: string;
      refresh_token: string;
      persistent?: boolean;
      expires_at?: string;
    }>("/auth/register", {
      email: payload.email,
      password: payload.password,
      name: payload.name,
      company_name: payload.companyName ?? null,
      language: payload.language,
      country_code: payload.countryCode,
      account_type: payload.accountType,
      business_use_confirmed: payload.businessUseConfirmed,
      adult_confirmed: payload.adultConfirmed,
      terms_version: payload.termsVersion,
      privacy_version: payload.privacyVersion,
    }),
  /** Consents the current user has on file (WP6 §2). */
  getConsents: () =>
    apiClient.get<{ items: UserConsent[] }>("/users/me/consents"),
  /** Record one accepted document version for the current user (WP6 §2). */
  acceptConsent: (consent: ConsentAcceptance) =>
    apiClient.post<void>("/users/me/consents", consent),
  /**
   * Public current versions of the legal documents (WP6). Until it ships
   * the request 404s and the constants in lib/legalVersions.ts stand in.
   */
  getLegalDocuments: () =>
    publicClient.get<LegalDocumentsResponse>("/legal/documents"),
  /**
   * Public country picker for registration (WP6): active dim_country rows
   * minus the blocked list, sorted by name. No auth, rate-limited.
   */
  getCountries: () =>
    publicClient.get<{
      items: Array<{ code: string; name: string; name_local: string | null }>;
    }>("/auth/countries"),
  getMe: () =>
    apiClient.get<{
      id: string;
      email: string;
      name: string;
      company_name: string | null;
      plan: string;
      trial_ends_at: string | null;
      language: string;
      timezone?: string | null;
      ai_tone?: string;
      default_currency?: string | null;
      created_at: string;
      telegram_chat_id: number | null;
      avatar_url: string | null;
      is_superuser?: boolean;
      is_active?: boolean;
      force_password_change?: boolean;
      preferences?: Record<string, unknown> | null;
      entitlements?: {
        service_tier: string;
        features: Record<string, boolean>;
        limits: Record<string, number>;
        trial_duration_days?: number;
        is_trial_expired?: boolean;
      };
    }>("/users/me"),
  updateMe: (data: {
    name?: string;
    company_name?: string;
    language?: string;
    timezone?: string;
    avatar_url?: string | null;
    ai_tone?: string;
    preferences?: Record<string, unknown>;
  }) => apiClient.put("/users/me", data),
  getTelegramLink: () =>
    apiClient.post<{ code: string; bot_url: string }>(
      "/telegram/generate-link-code",
    ),
  disconnectTelegram: () =>
    apiClient.post<{ unlinked: boolean }>("/telegram/unlink"),
};
