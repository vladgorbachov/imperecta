/**
 * /legal/:document — Terms, Privacy Policy, Acceptable Use Policy, Data
 * Sources & Bot Policy. Version line comes from the legal-documents
 * endpoint (or the bundled constants); body from the text registry, with
 * an explicit pending notice until counsel's texts land.
 */

import { useTranslation } from "react-i18next";
import { Link, Navigate, useParams } from "react-router-dom";
import { FileText } from "lucide-react";
import { useLegalDocuments } from "@/hooks/useLegalDocuments";
import { resolveLegalText, type LegalPageKey } from "@/content/legalTexts";
import type { LegalDocument } from "@/lib/legalVersions";
import { PublicPageShell } from "@/pages/legal/PublicPageShell";
import { BLOCKED_CONTACT_EMAIL } from "@/pages/BlockedCountryPage";

const PAGE_TITLES: Record<LegalPageKey, string> = {
  terms: "legal.terms",
  privacy: "legal.privacy",
  aup: "legal.aup",
  "data-sources": "legal.dataSources",
};

const VERSIONED: LegalDocument[] = ["terms", "privacy", "aup"];

function isLegalPageKey(value: string | undefined): value is LegalPageKey {
  return value != null && value in PAGE_TITLES;
}

export function LegalDocumentPage() {
  const { t, i18n } = useTranslation();
  const { document } = useParams<{ document: string }>();
  const documents = useLegalDocuments();

  if (!isLegalPageKey(document)) {
    return <Navigate to="/legal/terms" replace />;
  }

  const versioned = (VERSIONED as string[]).includes(document);
  const version = versioned ? documents[document as LegalDocument].version : null;
  const sections = resolveLegalText(document, i18n.language || "en");

  return (
    <PublicPageShell
      title={t(PAGE_TITLES[document])}
      meta={version ? t("legal.version", { version }) : undefined}
    >
      {sections ? (
        sections.map((section, index) => (
          <section key={index} className="space-y-2">
            {section.heading ? <h2 className="text-lg font-semibold">{section.heading}</h2> : null}
            {section.paragraphs.map((paragraph, paragraphIndex) => (
              <p key={paragraphIndex} className="text-muted-foreground">
                {paragraph}
              </p>
            ))}
          </section>
        ))
      ) : (
        <div
          className="flex items-start gap-3 rounded-md border border-[var(--glass-border)] bg-[var(--surface-sunken-bg)] p-4"
          data-testid="legal-text-pending"
        >
          <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          <div className="space-y-1">
            <p>{t("legal.textPending")}</p>
            <p className="text-muted-foreground">
              {t("legal.contact")}{" "}
              <a className="text-[var(--accent)] underline" href={`mailto:${BLOCKED_CONTACT_EMAIL}`}>
                {BLOCKED_CONTACT_EMAIL}
              </a>
            </p>
          </div>
        </div>
      )}
      {document === "data-sources" ? (
        <p>
          <Link to="/bot" className="text-[var(--accent)] underline-offset-2 hover:underline">
            {t("legal.optOutLink")}
          </Link>
        </p>
      ) : null}
    </PublicPageShell>
  );
}
