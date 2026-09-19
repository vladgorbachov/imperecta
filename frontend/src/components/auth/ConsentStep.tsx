/**
 * Re-consent step shown by the login page after `409 required_consents`:
 * a document version changed, the user must accept the current one before
 * the session is issued. Resubmits the same credentials with `consents`.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2 } from "lucide-react";
import type { ConsentAcceptance } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { useLegalDocuments } from "@/hooks/useLegalDocuments";
import type { LegalDocument } from "@/lib/legalVersions";
import { LegalConsentFields } from "@/components/auth/LegalConsentFields";
import { EMPTY_CONSENT_STATE, type ConsentFormState } from "@/lib/consentForm";

export interface ConsentStepProps {
  requiredDocuments: LegalDocument[];
  pending: boolean;
  onConfirm: (consents: ConsentAcceptance[]) => void;
  onCancel: () => void;
}

export function ConsentStep({ requiredDocuments, pending, onConfirm, onCancel }: ConsentStepProps) {
  const { t } = useTranslation();
  const documents = useLegalDocuments();
  const [state, setState] = useState<ConsentFormState>(EMPTY_CONSENT_STATE);

  return (
    <div className="space-y-6" data-testid="consent-step">
      <div className="space-y-2">
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">
          {t("auth.consentRequiredTitle")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("auth.consentRequiredBody")}</p>
      </div>
      <LegalConsentFields
        value={state}
        onChange={setState}
        documents={documents}
        requiredDocuments={requiredDocuments}
        documentsOnly
      />
      <div className="flex gap-2">
        <Button variant="outline" type="button" onClick={onCancel} disabled={pending}>
          {t("common.cancel")}
        </Button>
        <Button
          type="button"
          className="flex-1"
          disabled={!state.documentsAccepted || pending}
          onClick={() =>
            onConfirm(
              requiredDocuments.map((document) => ({
                document,
                version: documents[document].version,
              })),
            )
          }
        >
          {pending ? <Loader2 className="size-4 animate-spin" /> : t("auth.consentConfirm")}
        </Button>
      </div>
    </div>
  );
}
