/**
 * Settings → Consents: the document versions the user has accepted
 * (GET /users/me/consents, WP6 §2) with links to the current texts.
 */

import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { FileCheck } from "lucide-react";
import { authApi } from "@/api/auth";
import { DOCUMENT_LABELS } from "@/lib/consentForm";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useLegalDocuments } from "@/hooks/useLegalDocuments";
import { formatDate } from "@/lib/formatters";
import { LEGAL_DOCUMENTS, type LegalDocument } from "@/lib/legalVersions";

export function ConsentsCard() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const documents = useLegalDocuments();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["users", "me", "consents"],
    queryFn: () => authApi.getConsents().then((r) => r.data.items),
    staleTime: 60_000,
    retry: false,
  });

  const known = new Set(Object.keys(LEGAL_DOCUMENTS));
  const items = (data ?? []).filter((row) => known.has(row.document));

  return (
    <Card data-testid="consents-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileCheck className="size-4" />
          {t("settings.consents")}
        </CardTitle>
        <CardDescription>{t("settings.consentsDescription")}</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
          </div>
        ) : isError || items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("settings.consentsEmpty")}</p>
        ) : (
          <ul className="divide-y divide-[var(--glass-border)]">
            {items.map((row) => {
              const document = row.document as LegalDocument;
              const current = documents[document];
              const outdated = current.version !== row.version;
              return (
                <li key={`${row.document}-${row.version}`} className="flex items-center gap-3 py-2">
                  <div className="min-w-0 flex-1">
                    <Link
                      to={current.path}
                      target="_blank"
                      rel="noopener"
                      className="text-sm font-medium text-[var(--accent)] underline-offset-2 hover:underline"
                    >
                      {t(DOCUMENT_LABELS[document])}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      {t("settings.consentVersion", { version: row.version })} ·{" "}
                      {t("settings.consentAccepted", { date: formatDate(row.accepted_at, locale) })}
                    </p>
                  </div>
                  {outdated ? (
                    <span className="label-mono !text-[var(--status-warn)]">
                      {t("settings.consentOutdated")}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
