import axios from "axios";
import type { RequiredConsent } from "@/api/auth";
import { LEGAL_DOCUMENTS, type LegalDocument } from "@/lib/legalVersions";

const CONSENT_DETAILS = new Set(["consent_required", "consent_version_outdated"]);

/**
 * Reads the WP6 consent errors: `409 {"detail":"consent_required",
 * "required_consents":[…]}` on login and `422 consent_version_outdated` on
 * registration. Returns the documents to accept, or null for other errors.
 */
export function requiredConsentsFromError(error: unknown): LegalDocument[] | null {
  if (!axios.isAxiosError(error)) {
    return null;
  }
  const data = error.response?.data as
    | { detail?: unknown; required_consents?: RequiredConsent[] }
    | undefined;
  if (typeof data?.detail !== "string" || !CONSENT_DETAILS.has(data.detail)) {
    return null;
  }
  const known = new Set(Object.keys(LEGAL_DOCUMENTS));
  const documents = (data.required_consents ?? [])
    .map((row) => row.document)
    .filter((document): document is LegalDocument => known.has(document));
  return documents.length > 0 ? documents : (["terms", "privacy"] as LegalDocument[]);
}
