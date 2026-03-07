/**
 * Digests page: card grid of digests, DigestModal for viewing.
 *
 * i18n keys used:
 * - nav.digests
 * - digests.typeDaily, digests.typeWeekly, digests.sent, digests.draft
 * - digests.view, digests.resend
 * - digests.emptyTitle, digests.emptyHint
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { formatPeriodRange, formatRelativeTime } from "@/lib/formatters";
import { useQuery } from "@tanstack/react-query";
import { digestsApi } from "@/api/digests";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { FileText, Mail, MessageCircle } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import type { Digest } from "@/api/digests";

function renderMarkdown(md: string): string {
  if (!md) return "";
  let out = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/^# (.*)$/gm, '<h1 class="digest-h1">$1</h1>')
    .replace(/^## (.*)$/gm, '<h2 class="digest-h2">$1</h2>')
    .replace(/^### (.*)$/gm, '<h3 class="digest-h3">$1</h3>')
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`(.*?)`/g, '<code class="digest-code">$1</code>')
    .replace(/^- (.*)$/gm, "<li>$1</li>");
  out = out.replace(/(<li>.*?<\/li>\n?)+/gs, (m) => `<ul class="digest-ul">${m}</ul>`);
  out = out.replace(/\n\n+/g, "<br/><br/>").replace(/\n/g, "<br/>");
  return out;
}

export function DigestsPage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const [modalDigestId, setModalDigestId] = useState<string | null>(null);

  const { data: digests = [], isLoading } = useQuery({
    queryKey: ["digests"],
    queryFn: async () => {
      const { data } = await digestsApi.list();
      return data;
    },
  });

  const { data: modalDigest } = useQuery({
    queryKey: ["digests", modalDigestId],
    queryFn: async () => {
      if (!modalDigestId) return null;
      const { data } = await digestsApi.get(modalDigestId);
      return data;
    },
    enabled: !!modalDigestId,
  });

  return (
    <div className="space-y-6">
      <PageHeader title="nav.digests" />

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-48 rounded-lg" />
          ))}
        </div>
      ) : digests.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="digests.emptyTitle"
          description="digests.emptyHint"
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {digests.map((d) => (
            <DigestCard
              key={d.id}
              digest={d}
              locale={locale}
              onView={() => setModalDigestId(d.id)}
            />
          ))}
        </div>
      )}

      {modalDigestId && (
        <DigestModal
          digest={modalDigest}
          locale={locale}
          onClose={() => setModalDigestId(null)}
        />
      )}
    </div>
  );
}

function DigestCard({
  digest,
  locale,
  onView,
}: {
  digest: Digest;
  locale: string;
  onView: () => void;
}) {
  const { t } = useTranslation();
  const isDaily = digest.period_type === "daily";
  const isSent = !!digest.sent_at;

  return (
    <Card className="flex flex-col">
      <CardContent className="flex flex-1 flex-col gap-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Badge
            variant="secondary"
            className={
              isDaily
                ? "bg-blue-500/15 text-blue-700 border-blue-500/30 dark:bg-blue-500/20 dark:text-blue-400 dark:border-blue-500/40"
                : "bg-purple-500/15 text-purple-700 border-purple-500/30 dark:bg-purple-500/20 dark:text-purple-400 dark:border-purple-500/40"
            }
          >
            {isDaily ? t("digests.typeDaily") : t("digests.typeWeekly")}
          </Badge>
          <Badge
            variant="secondary"
            className={
              isSent
                ? "bg-green-500/15 text-green-700 border-green-500/30 dark:bg-green-500/20 dark:text-green-400 dark:border-green-500/40"
                : "bg-neutral-500/15 text-neutral-600 border-neutral-500/30 dark:bg-neutral-500/20 dark:text-neutral-400 dark:border-neutral-500/40"
            }
          >
            {isSent ? t("digests.sent") : t("digests.draft")}
          </Badge>
        </div>

        <p className="text-sm font-medium">
          {formatPeriodRange(digest.period_start, digest.period_end, locale)}
        </p>

        <p className="text-xs text-muted-foreground dark:text-muted-foreground">
          {t("digests.created")} {formatRelativeTime(digest.created_at, locale)}
        </p>

        <div className="mt-auto flex items-center justify-between gap-2 pt-2">
          <div className="flex gap-1.5">
            <Mail className="size-4 text-muted-foreground dark:text-muted-foreground" />
            <MessageCircle className="size-4 text-muted-foreground dark:text-muted-foreground" />
          </div>
          <Button size="sm" onClick={onView}>
            {t("digests.view")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function DigestModal({
  digest,
  locale,
  onClose,
}: {
  digest: Digest | null | undefined;
  locale: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();

  if (!digest) {
    return (
      <Dialog open onOpenChange={() => onClose()}>
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-hidden sm:max-w-3xl">
          <div className="flex items-center justify-center py-12">
            <Skeleton className="h-64 w-full" />
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  const isDaily = digest.period_type === "daily";
  const content = digest.content_md?.trim() || "";

  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-hidden sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <span>
              {isDaily ? t("digests.typeDaily") : t("digests.typeWeekly")}
            </span>
            <span className="text-muted-foreground dark:text-muted-foreground">
              —
            </span>
            <span>
              {formatPeriodRange(digest.period_start, digest.period_end, locale)}
            </span>
          </DialogTitle>
        </DialogHeader>

        <div
          className="digest-content max-h-[60vh] overflow-y-auto rounded-md border border-border bg-muted/30 p-4 dark:bg-muted/20"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
        />

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t("common.close")}
          </Button>
          <Button variant="outline">{t("digests.resend")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
