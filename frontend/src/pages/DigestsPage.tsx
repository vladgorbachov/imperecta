// MOBILE-2026: fully responsive + bottom nav + drawer

/**
 * Digests page: 3 tabs (Weekly, Daily Pro, Strategic), cards with preview, modal, AI chat link.
 * i18n: nav.digests, digests.*, common.*
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { formatPeriodRange, formatRelativeTime } from "@/lib/formatters";
import { useQuery } from "@tanstack/react-query";
import { digestsApi } from "@/api/digests";
import { useAuthStore } from "@/stores/authStore";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { FileText, MessageCircle, Sparkles, Lock } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
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

function previewText(text: string, maxLen: number): string {
  const stripped = text.replace(/\s+/g, " ").trim();
  if (stripped.length <= maxLen) return stripped;
  return stripped.slice(0, maxLen) + "…";
}

export function DigestsPage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const navigate = useNavigate();
  const plan = (useAuthStore((s) => s.user?.plan) ?? "trial").toLowerCase();
  const isPro = plan === "pro";

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

  const weeklyDigests = digests.filter((d) => d.period_type === "weekly");
  const dailyDigests = digests.filter((d) => d.period_type === "daily");

  const handleDiscussWithAi = (digestId: string) => {
    navigate({ pathname: "/ai", search: `?digest_id=${digestId}` });
    // TODO: POST /api/ai/chat with context: digest_id
  };

  return (
    <div className="space-y-6">
      <PageHeader title="nav.digests" />

      <Tabs defaultValue="weekly">
        <TabsList className="w-full flex-wrap sm:w-auto">
          <TabsTrigger value="weekly">{t("digests.tabWeekly")}</TabsTrigger>
          <TabsTrigger value="daily">
            {t("digests.tabDaily")} {!isPro && <Lock className="ml-1 size-3" />}
          </TabsTrigger>
          <TabsTrigger value="strategic">{t("digests.tabStrategic")}</TabsTrigger>
        </TabsList>

        <TabsContent value="weekly" className="mt-6">
          {isLoading ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-48 rounded-lg" />
              ))}
            </div>
          ) : weeklyDigests.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="digests.emptyTitle"
              description="digests.emptyHint"
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {weeklyDigests.map((d) => (
                <DigestCard
                  key={d.id}
                  digest={d}
                  locale={locale}
                  onView={() => setModalDigestId(d.id)}
                  onDiscussWithAi={() => handleDiscussWithAi(d.id)}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="daily" className="mt-6">
          <div className={cn("relative", !isPro && "pointer-events-none")}>
            {!isPro && (
              <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-background/80 backdrop-blur-sm dark:bg-background/90">
                <div className="rounded-lg border border-border bg-card px-6 py-4 shadow-lg dark:border-border dark:bg-card">
                  <Lock className="mx-auto mb-2 size-10 text-muted-foreground" />
                  <p className="text-center font-medium">{t("digests.availableInPro")}</p>
                </div>
              </div>
            )}
            {isLoading ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-48 rounded-lg" />
                ))}
              </div>
            ) : dailyDigests.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="digests.emptyTitle"
                description="digests.emptyHint"
              />
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {dailyDigests.map((d) => (
                  <DigestCard
                    key={d.id}
                    digest={d}
                    locale={locale}
                    onView={() => setModalDigestId(d.id)}
                    onDiscussWithAi={() => handleDiscussWithAi(d.id)}
                  />
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="strategic" className="mt-6">
          <EmptyState
            icon={FileText}
            title="digests.strategicComingSoon"
            description="digests.strategicComingSoonDesc"
          />
        </TabsContent>
      </Tabs>

      {modalDigestId && (
        <DigestModal
          digest={modalDigest}
          locale={locale}
          onClose={() => setModalDigestId(null)}
          onDiscussWithAi={() => handleDiscussWithAi(modalDigestId)}
        />
      )}
    </div>
  );
}

function DigestCard({
  digest,
  locale,
  onView,
  onDiscussWithAi,
}: {
  digest: Digest;
  locale: string;
  onView: () => void;
  onDiscussWithAi: () => void;
}) {
  const { t } = useTranslation();
  const isDaily = digest.period_type === "daily";
  const isSent = !!digest.sent_at;
  const preview = previewText(digest.content_md ?? "", 100);

  return (
    <Card
      className="cursor-pointer transition-colors hover:bg-muted/50 dark:hover:bg-muted/30"
      onClick={onView}
    >
      <CardContent className="flex flex-1 flex-col gap-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Badge
            variant="secondary"
            className={
              isDaily
                ? "border bg-[var(--accent-bg)] text-[var(--accent)] border-[var(--accent-border)]"
                : "border bg-[var(--accent2-bg)] text-[var(--accent2)] border-[var(--accent2-border)]"
            }
          >
            {isDaily ? t("digests.typeDaily") : t("digests.typeWeekly")}
          </Badge>
          <Badge
            variant="secondary"
            className={
              isSent
                ? "border bg-[var(--color-price-down-bg)] text-[var(--color-price-down)] border-[var(--color-price-down-border)]"
                : "border bg-[var(--color-muted-bg)] text-[var(--foreground-muted)] border-[var(--glass-border)]"
            }
          >
            {isSent ? t("digests.sent") : t("digests.draft")}
          </Badge>
        </div>

        <p className="text-sm font-medium">
          {formatPeriodRange(digest.period_start, digest.period_end, locale)}
        </p>

        <p className="line-clamp-3 text-xs text-muted-foreground dark:text-muted-foreground">
          {preview || t("digests.noPreview")}
        </p>

        <p className="text-xs text-muted-foreground dark:text-muted-foreground">
          {t("digests.created")} {formatRelativeTime(digest.created_at, locale)}
        </p>

        <div className="mt-auto flex flex-wrap items-center gap-2 pt-2">
          <Button size="sm" onClick={(e) => { e.stopPropagation(); onView(); }}>
            {t("digests.view")}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={(e) => {
              e.stopPropagation();
              onDiscussWithAi();
            }}
          >
            <Sparkles className="mr-2 size-4" />
            {t("digests.discussWithAi")}
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
  onDiscussWithAi,
}: {
  digest: Digest | null | undefined;
  locale: string;
  onClose: () => void;
  onDiscussWithAi: () => void;
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
            <span className="text-muted-foreground">—</span>
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
          <Button onClick={onDiscussWithAi}>
            <MessageCircle className="mr-2 size-4" />
            {t("digests.discussWithAi")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
