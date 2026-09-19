/**
 * Compliance → Blocked countries: the runtime sanctions/exclusion list the
 * backend enforces on registration, login, geo-IP and source onboarding
 * (LEGAL_CLEANUP_PLAN §6.6). Review banner, searchable table, add/edit/
 * remove dialogs, audit drawer and a geo-provider IP check for debugging.
 */

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import {
  AlertTriangle,
  CalendarCheck,
  Pencil,
  Plus,
  ScrollText,
  Search,
  ShieldBan,
  Trash2,
} from "lucide-react";
import type { BlockedCountry, IpCountryCheck } from "@/api/admin";
import {
  useBlockedCountries,
  useCheckIpCountry,
  useCompleteReview,
  useRemoveBlockedCountry,
} from "@/hooks/useAdmin";
import { BlockedCountryAddDialog } from "@/components/admin/compliance/BlockedCountryAddDialog";
import { BlockedCountryAuditDrawer } from "@/components/admin/compliance/BlockedCountryAuditDrawer";
import {
  REASON_BADGE_CLASS,
  REASON_LABELS,
} from "@/components/admin/compliance/reasonBadge";
import { flagForCode } from "@/lib/countryFlag";
import { describeDetail, errorDetail } from "@/components/admin/compliance/complianceErrors";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { formatDate } from "@/lib/formatters";
import { cn } from "@/lib/utils";

const BASIS_PREVIEW_CHARS = 40;
const IPV4 = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/;
const IPV6 = /^[0-9a-fA-F:]{2,39}$/;

function isPast(date: string): boolean {
  const value = Date.parse(date);
  return Number.isFinite(value) && value < Date.now();
}

function ReviewBanner({
  lastReviewedAt,
  nextReviewDueAt,
  onMarkComplete,
  locale,
}: {
  lastReviewedAt: string | null;
  nextReviewDueAt: string;
  onMarkComplete: () => void;
  locale: string;
}) {
  const { t } = useTranslation();
  const overdue = isPast(nextReviewDueAt);
  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 rounded-md border px-3 py-2",
        overdue
          ? "border-[var(--status-warn-border)] bg-[var(--status-warn-bg)]"
          : "border-[var(--glass-border)] bg-[var(--surface-sunken-bg)]",
      )}
      data-testid="review-banner"
    >
      <div className="flex min-w-0 items-center gap-2 text-sm">
        {overdue ? (
          <AlertTriangle className="size-4 shrink-0 text-[var(--status-warn)]" />
        ) : (
          <CalendarCheck className="size-4 shrink-0 text-muted-foreground" />
        )}
        <span className="min-w-0">
          {overdue ? (
            <span className="font-medium">{t("admin.compliance.review.overdue")} · </span>
          ) : null}
          {t("admin.compliance.review.last")}:{" "}
          <span className="font-medium">
            {lastReviewedAt
              ? formatDate(lastReviewedAt, locale)
              : t("admin.compliance.review.never")}
          </span>{" "}
          · {t("admin.compliance.review.next")}:{" "}
          <span className={cn("font-medium", overdue && "text-[var(--status-warn)]")}>
            {formatDate(nextReviewDueAt, locale)}
          </span>
        </span>
      </div>
      <Button variant="outline" size="sm" onClick={onMarkComplete}>
        {t("admin.compliance.review.markComplete")}
      </Button>
    </div>
  );
}

function IpCheckForm() {
  const { t } = useTranslation();
  const [ip, setIp] = useState("");
  const [result, setResult] = useState<IpCountryCheck | null>(null);
  const check = useCheckIpCountry();
  const ipValid = IPV4.test(ip.trim()) || IPV6.test(ip.trim());

  const run = async () => {
    try {
      setResult(await check.mutateAsync(ip.trim()));
    } catch (error) {
      setResult(null);
      toast.error(describeDetail(errorDetail(error), t("admin.compliance.errors.generic")));
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-[var(--glass-border)] pt-3">
      <span className="label-mono">{t("admin.compliance.ipCheck.title")}</span>
      <Input
        value={ip}
        onChange={(event) => setIp(event.target.value)}
        placeholder={t("admin.compliance.ipCheck.placeholder")}
        className="h-8 w-56 font-mono text-xs"
        aria-label={t("admin.compliance.ipCheck.title")}
      />
      <Button variant="outline" size="sm" disabled={!ipValid || check.isPending} onClick={() => void run()}>
        {t("admin.compliance.ipCheck.button")}
      </Button>
      {result ? (
        <span className="text-xs" data-testid="ip-check-result">
          <span className="font-mono">{result.ip}</span> →{" "}
          {result.country ? (
            <>
              <span aria-hidden>{flagForCode(result.country)}</span>{" "}
              <span className="font-mono">{result.country}</span>
            </>
          ) : (
            t("admin.compliance.ipCheck.unknown")
          )}{" "}
          ·{" "}
          <span
            className={cn(
              "font-medium",
              result.blocked ? "text-[var(--status-error)]" : "text-[var(--status-ok)]",
            )}
          >
            {result.blocked
              ? t("admin.compliance.ipCheck.blocked")
              : t("admin.compliance.ipCheck.allowed")}
          </span>{" "}
          <span className="text-muted-foreground">({result.provider})</span>
        </span>
      ) : null}
    </div>
  );
}

export function BlockedCountriesSection() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const { data, isLoading, isError, refetch } = useBlockedCountries();
  const removeCountry = useRemoveBlockedCountry();
  const completeReview = useCompleteReview();

  const [search, setSearch] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<BlockedCountry | null>(null);
  const [removing, setRemoving] = useState<BlockedCountry | null>(null);
  const [auditOpen, setAuditOpen] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewNote, setReviewNote] = useState("");

  const rows = useMemo(() => {
    const query = search.trim().toLowerCase();
    return [...(data?.items ?? [])]
      .filter(
        (row) =>
          !query ||
          row.country_code.toLowerCase().includes(query) ||
          row.name.toLowerCase().includes(query),
      )
      .sort((a, b) => a.country_code.localeCompare(b.country_code));
  }, [data?.items, search]);

  const confirmRemove = async () => {
    if (!removing) {
      return;
    }
    try {
      await removeCountry.mutateAsync(removing.country_code);
      toast.success(t("admin.compliance.remove.success", { country: removing.name }));
      setRemoving(null);
    } catch (error) {
      toast.error(describeDetail(errorDetail(error), t("admin.compliance.errors.generic")));
    }
  };

  const confirmReview = async () => {
    try {
      await completeReview.mutateAsync(reviewNote.trim() || undefined);
      toast.success(t("admin.compliance.review.done"));
      setReviewOpen(false);
      setReviewNote("");
    } catch (error) {
      toast.error(describeDetail(errorDetail(error), t("admin.compliance.errors.generic")));
    }
  };

  return (
    <Card data-testid="blocked-countries-section">
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ShieldBan className="size-4" />
              {t("admin.compliance.blocked.title")}
            </CardTitle>
            <CardDescription>{t("admin.compliance.blocked.subtitle")}</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setAuditOpen(true)}>
              <ScrollText className="me-1.5 size-3.5" />
              {t("admin.compliance.audit.button")}
            </Button>
            <Button size="sm" onClick={() => setAddOpen(true)}>
              <Plus className="me-1.5 size-3.5" />
              {t("admin.compliance.add.button")}
            </Button>
          </div>
        </div>
        {data ? (
          <ReviewBanner
            lastReviewedAt={data.last_reviewed_at}
            nextReviewDueAt={data.next_review_due_at}
            onMarkComplete={() => setReviewOpen(true)}
            locale={locale}
          />
        ) : null}
        <div className="relative max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("admin.compliance.search")}
            className="h-8 pl-8"
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <div className="space-y-2" data-testid="blocked-countries-skeleton">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : isError ? (
          <EmptyState
            title={t("common.error")}
            description={t("admin.compliance.errors.load")}
            action={{ label: t("admin.compliance.errors.retry"), onClick: () => void refetch() }}
          />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={ShieldBan}
            title={t("admin.compliance.empty")}
            description={t("admin.compliance.emptyHint")}
          />
        ) : (
          <div className="overflow-x-auto">
            <Table className="min-w-[960px]">
              <TableHeader>
                <TableRow>
                  <TableHead>{t("admin.compliance.table.country")}</TableHead>
                  <TableHead>{t("admin.compliance.table.reason")}</TableHead>
                  <TableHead>{t("admin.compliance.table.basis")}</TableHead>
                  <TableHead>{t("admin.compliance.table.note")}</TableHead>
                  <TableHead>{t("admin.compliance.table.addedBy")}</TableHead>
                  <TableHead>{t("admin.compliance.table.reviewDue")}</TableHead>
                  <TableHead className="text-right">{t("admin.compliance.table.affectedUsers")}</TableHead>
                  <TableHead className="text-right">{t("admin.compliance.table.affectedMarketplaces")}</TableHead>
                  <TableHead className="text-right">{t("admin.compliance.table.actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => {
                  const overdue = isPast(row.review_due_at);
                  const basisLong = row.basis.length > BASIS_PREVIEW_CHARS;
                  return (
                    <TableRow key={row.country_code} data-testid={`blocked-row-${row.country_code}`}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span aria-hidden>{flagForCode(row.country_code)}</span>
                          <span className="font-mono text-xs">{row.country_code}</span>
                          <span className="font-medium">{row.name}</span>
                          {row.is_protected ? (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <AlertTriangle className="size-3.5 text-[var(--status-warn)]" />
                              </TooltipTrigger>
                              <TooltipContent>{t("admin.compliance.add.protectedHint")}</TooltipContent>
                            </Tooltip>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            "label-mono inline-flex rounded border px-1.5 py-0.5",
                            REASON_BADGE_CLASS[row.reason],
                          )}
                        >
                          {t(REASON_LABELS[row.reason])}
                        </span>
                      </TableCell>
                      <TableCell className="max-w-[220px]">
                        {basisLong ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="block truncate text-xs">{row.basis}</span>
                            </TooltipTrigger>
                            <TooltipContent className="max-w-sm">{row.basis}</TooltipContent>
                          </Tooltip>
                        ) : (
                          <span className="text-xs">{row.basis}</span>
                        )}
                      </TableCell>
                      <TableCell className="max-w-[180px]">
                        <span className="block truncate text-xs text-muted-foreground">
                          {row.note ?? "—"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="block text-xs">
                          {row.added_by?.email ?? t("admin.compliance.table.seeded")}
                        </span>
                        <span className="block text-2xs text-muted-foreground">
                          {formatDate(row.added_at, locale)}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            "text-xs tabular-nums",
                            overdue && "font-medium text-[var(--status-error)]",
                          )}
                        >
                          {formatDate(row.review_due_at, locale)}
                        </span>
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">
                        {row.affected_users}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs tabular-nums">
                        {row.affected_marketplaces}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-7"
                            aria-label={t("common.edit")}
                            onClick={() => setEditing(row)}
                          >
                            <Pencil className="size-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-7 text-destructive"
                            aria-label={t("common.delete")}
                            onClick={() => setRemoving(row)}
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
        <IpCheckForm />
      </CardContent>

      <BlockedCountryAddDialog open={addOpen} onOpenChange={setAddOpen} />
      <BlockedCountryAddDialog
        open={editing != null}
        onOpenChange={(next) => {
          if (!next) {
            setEditing(null);
          }
        }}
        editing={editing}
      />
      <BlockedCountryAuditDrawer open={auditOpen} onOpenChange={setAuditOpen} />

      {/* Remove confirmation */}
      <Dialog open={removing != null} onOpenChange={(next) => (!next ? setRemoving(null) : null)}>
        <DialogContent className="surface-overlay sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("admin.compliance.remove.title")}</DialogTitle>
            <DialogDescription>
              {removing
                ? t("admin.compliance.remove.body", { country: removing.name })
                : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRemoving(null)} disabled={removeCountry.isPending}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={removeCountry.isPending}
              onClick={() => void confirmRemove()}
            >
              {t("admin.compliance.remove.confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Review confirmation */}
      <Dialog
        open={reviewOpen}
        onOpenChange={(next) => {
          if (!next) {
            setReviewOpen(false);
            setReviewNote("");
          }
        }}
      >
        <DialogContent className="surface-overlay sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("admin.compliance.review.confirmTitle")}</DialogTitle>
            <DialogDescription>{t("admin.compliance.review.confirmBody")}</DialogDescription>
          </DialogHeader>
          <Input
            value={reviewNote}
            onChange={(event) => setReviewNote(event.target.value)}
            placeholder={t("admin.compliance.review.notePlaceholder")}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setReviewOpen(false)} disabled={completeReview.isPending}>
              {t("common.cancel")}
            </Button>
            <Button disabled={completeReview.isPending} onClick={() => void confirmReview()}>
              {t("admin.compliance.review.markComplete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
