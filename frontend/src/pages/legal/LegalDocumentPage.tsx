/**
 * /legal/:document — Terms, Privacy Policy, Acceptable Use Policy, Data
 * Sources & Bot Policy. The backend is the single source of truth for both
 * version and text (GET /legal/documents/{document}?lang=xx, markdown):
 * consent versions can never drift from what the user read. A document
 * counsel has not delivered yet answers 404 document_not_available and the
 * page shows an explicit pending notice — never placeholder text.
 */

import { useTranslation } from "react-i18next";
import { Link, Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { authApi } from "@/api/auth";
import { Skeleton } from "@/components/ui/skeleton";
import { useLegalDocuments } from "@/hooks/useLegalDocuments";
import { formatDate } from "@/lib/formatters";
import type { LegalDocument } from "@/lib/legalVersions";
import { PublicPageShell } from "@/pages/legal/PublicPageShell";
import { BLOCKED_CONTACT_EMAIL } from "@/pages/BlockedCountryPage";

type LegalPageKey = LegalDocument | "data-sources";

const PAGE_TITLES: Record<LegalPageKey, string> = {
  terms: "legal.terms",
  privacy: "legal.privacy",
  aup: "legal.aup",
  "data-sources": "legal.dataSources",
};

/** URL slug → backend document id. */
const DOCUMENT_IDS: Record<LegalPageKey, string> = {
  terms: "terms",
  privacy: "privacy",
  aup: "aup",
  "data-sources": "data_sources",
};

function isLegalPageKey(value: string | undefined): value is LegalPageKey {
  return value != null && value in PAGE_TITLES;
}

const MARKDOWN_COMPONENTS = {
  h1: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="mt-6 text-xl font-semibold first:mt-0">{children}</h2>
  ),
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="mt-6 text-lg font-semibold first:mt-0">{children}</h2>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="mt-4 text-base font-semibold">{children}</h3>
  ),
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="my-2 text-muted-foreground">{children}</p>
  ),
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="my-2 list-disc space-y-1 ps-5 text-muted-foreground">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="my-2 list-decimal space-y-1 ps-5 text-muted-foreground">{children}</ol>
  ),
  a: ({ children, href }: { children?: React.ReactNode; href?: string }) => (
    <a href={href} className="text-[var(--accent)] underline-offset-2 hover:underline" rel="noopener">
      {children}
    </a>
  ),
};

export function LegalDocumentPage() {
  const { t, i18n } = useTranslation();
  const { document } = useParams<{ document: string }>();
  const documents = useLegalDocuments();
  const locale = i18n.language || "en";
  const lang = locale.split("-")[0];
  const pageKey = isLegalPageKey(document) ? document : null;

  const { data: text, isLoading, isError } = useQuery({
    queryKey: ["legal", "document-text", pageKey, lang],
    queryFn: () => authApi.getLegalDocumentText(DOCUMENT_IDS[pageKey!], lang).then((r) => r.data),
    enabled: pageKey != null,
    staleTime: 60 * 60 * 1000,
    retry: false,
  });

  if (!pageKey) {
    return <Navigate to="/legal/terms" replace />;
  }

  const version = text?.version ?? (pageKey === "data-sources" ? null : documents[pageKey].version);

  return (
    <PublicPageShell
      title={t(PAGE_TITLES[pageKey])}
      meta={
        version ? (
          <>
            {t("legal.version", { version })}
            {text?.updated_at ? ` · ${formatDate(text.updated_at, locale)}` : null}
          </>
        ) : undefined
      }
    >
      {isLoading ? (
        <div className="space-y-2" data-testid="legal-text-loading">
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-5/6" />
        </div>
      ) : text && !isError ? (
        <article data-testid="legal-text" lang={text.lang}>
          <ReactMarkdown components={MARKDOWN_COMPONENTS}>{text.body}</ReactMarkdown>
        </article>
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
      {pageKey === "data-sources" ? (
        <p>
          <Link to="/bot" className="text-[var(--accent)] underline-offset-2 hover:underline">
            {t("legal.optOutLink")}
          </Link>
        </p>
      ) : null}
    </PublicPageShell>
  );
}
