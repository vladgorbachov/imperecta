/**
 * Registration consents (WP6 / F5): account type, business-use and adult
 * confirmations, acceptance of the Terms and the Privacy Policy with the
 * document versions shown. The same acceptance block serves the re-consent
 * step on login (`documentsOnly`).
 */

import { Trans, useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Checkbox } from "@/components/ui/checkbox";
import {
  ACCOUNT_TYPE_LABELS,
  DOCUMENT_LABELS,
  type ConsentFormState,
} from "@/lib/consentForm";
import { ACCOUNT_TYPES, type LegalDocument, type LegalDocumentRef } from "@/lib/legalVersions";
import { cn } from "@/lib/utils";

export interface LegalConsentFieldsProps {
  value: ConsentFormState;
  onChange: (next: ConsentFormState) => void;
  documents: Record<LegalDocument, LegalDocumentRef>;
  /** Which documents the acceptance line covers. */
  requiredDocuments: LegalDocument[];
  error?: string;
  /** Re-consent on login: only the document acceptance line. */
  documentsOnly?: boolean;
}

export function LegalConsentFields({
  value,
  onChange,
  documents,
  requiredDocuments,
  error,
  documentsOnly = false,
}: LegalConsentFieldsProps) {
  const { t } = useTranslation();
  const set = (patch: Partial<ConsentFormState>) => onChange({ ...value, ...patch });

  const documentLink = (document: LegalDocument) => (
    <Link
      to={documents[document].path}
      target="_blank"
      rel="noopener"
      className="text-[var(--accent)] underline-offset-2 hover:underline"
    />
  );

  return (
    <div className="space-y-4" data-testid="legal-consent-fields">
      {!documentsOnly ? (
        <>
          <div className="space-y-2">
            <p className="text-sm font-medium">{t("auth.accountType.label")}</p>
            <div
              className="grid grid-cols-2 gap-2"
              role="radiogroup"
              aria-label={t("auth.accountType.label")}
            >
              {ACCOUNT_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  role="radio"
                  aria-checked={value.accountType === type}
                  onClick={() => set({ accountType: type })}
                  className={cn(
                    "rounded-md border px-3 py-2 text-sm transition-colors",
                    value.accountType === type
                      ? "border-[var(--accent-border)] bg-[var(--accent-bg-subtle)] font-medium"
                      : "border-input hover:border-[var(--glass-border-hover)]",
                  )}
                >
                  {t(ACCOUNT_TYPE_LABELS[type])}
                </button>
              ))}
            </div>
          </div>

          <label className="flex items-start gap-2.5 text-sm">
            <Checkbox
              checked={value.businessUseConfirmed}
              onCheckedChange={(checked) => set({ businessUseConfirmed: checked === true })}
              className="mt-0.5"
              aria-label={t("auth.businessUseConfirm")}
            />
            <span>{t("auth.businessUseConfirm")}</span>
          </label>

          <label className="flex items-start gap-2.5 text-sm">
            <Checkbox
              checked={value.adultConfirmed}
              onCheckedChange={(checked) => set({ adultConfirmed: checked === true })}
              className="mt-0.5"
              aria-label={t("auth.adultConfirm")}
            />
            <span>{t("auth.adultConfirm")}</span>
          </label>
        </>
      ) : null}

      <label className="flex items-start gap-2.5 text-sm">
        <Checkbox
          checked={value.documentsAccepted}
          onCheckedChange={(checked) => set({ documentsAccepted: checked === true })}
          className="mt-0.5"
          aria-label={t("auth.acceptDocuments.aria")}
        />
        <span>
          <Trans
            i18nKey="auth.acceptDocuments.text"
            components={{ terms: documentLink("terms"), privacy: documentLink("privacy") }}
          />
          <span className="mt-0.5 block font-mono text-2xs text-muted-foreground">
            {requiredDocuments
              .map((document) => `${t(DOCUMENT_LABELS[document])} ${documents[document].version}`)
              .join(" · ")}
          </span>
        </span>
      </label>

      {error ? <p className="text-xs text-destructive dark:text-destructive">{error}</p> : null}
    </div>
  );
}
