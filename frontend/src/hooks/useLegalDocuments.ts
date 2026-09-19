/**
 * Current versions of the legal documents. Source of truth is the public
 * GET /legal/documents (WP6); until it ships the request 404s and the
 * bundled constants in lib/legalVersions.ts stand in.
 */

import { useQuery } from "@tanstack/react-query";
import { authApi } from "@/api/auth";
import { LEGAL_DOCUMENTS, type LegalDocument, type LegalDocumentRef } from "@/lib/legalVersions";

export function useLegalDocuments(): Record<LegalDocument, LegalDocumentRef> {
  const query = useQuery({
    queryKey: ["legal", "documents"],
    queryFn: () => authApi.getLegalDocuments().then((r) => r.data),
    staleTime: 60 * 60 * 1000,
    retry: false,
  });

  if (!query.data) {
    return LEGAL_DOCUMENTS;
  }
  const merged = { ...LEGAL_DOCUMENTS };
  for (const document of Object.keys(merged) as LegalDocument[]) {
    const row = query.data[document];
    if (row) {
      /* `url` is the API text endpoint; the in-app page path stays ours. */
      merged[document] = { ...merged[document], version: row.version };
    }
  }
  return merged;
}
