/**
 * Legal documents the user consents to at registration (WP6 / F5).
 * Versions are the bootstrap fallback ONLY: the public documents endpoint
 * (see useLegalDocuments) is the source of truth once the backend ships it,
 * and the values below must then match what counsel publishes. The
 * placeholder version is the plan date, flagged in the F5 report.
 */

export type LegalDocument = "terms" | "privacy" | "aup";

export interface LegalDocumentRef {
  document: LegalDocument;
  version: string;
  /** In-app route of the document text (F8 pages). */
  path: string;
}

export const LEGAL_DOCUMENTS: Record<LegalDocument, LegalDocumentRef> = {
  terms: { document: "terms", version: "2026-09-19", path: "/legal/terms" },
  privacy: { document: "privacy", version: "2026-09-19", path: "/legal/privacy" },
  aup: { document: "aup", version: "2026-09-19", path: "/legal/aup" },
};

/** Documents that must be accepted to create an account. */
export const SIGNUP_CONSENT_DOCUMENTS: LegalDocument[] = ["terms", "privacy"];

export type AccountType = "business" | "sole_trader";
export const ACCOUNT_TYPES: AccountType[] = ["business", "sole_trader"];
